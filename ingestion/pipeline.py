"""
Pipeline de ingestão e enriquecimento de dados
Fluxo: CSV bruto → validação → normalização → enriquecimento → banco
"""
import pandas as pd
import numpy as np
from datetime import date, datetime
from typing import Dict, List, Tuple
from sqlalchemy.orm import Session
from core.database import (
    Eleitor, LoteImportacao, BairroRef, ZonaEleitoral,
    SecaoEleitoral, EventoCampanha, MetricaRedeSocial,
    PostRedeSocial, AlcanceGeografico, Voluntario
)

# ── Mapeamentos de normalização ──────────────────────────────────

COL_ALIASES = {
    "nome": ["nome", "name", "eleitor", "cadastrado", "apoiador"],
    "bairro": ["bairro", "neighborhood", "bairro_residencia", "local"],
    "zona": ["zona", "zone", "zona_eleitoral", "num_zona"],
    "genero": ["genero", "gênero", "sexo", "gender", "sex"],
    "idade": ["idade", "age", "anos"],
    "data_nascimento": ["data_nascimento", "nascimento", "dt_nasc", "dob"],
    "telefone": ["telefone", "phone", "celular", "cel", "contato", "whatsapp"],
    "escolaridade": ["escolaridade", "escol", "education", "grau"],
    "profissao": ["profissao", "profissão", "occupation", "cargo_profissional"],
    "origem": ["origem", "source", "como_chegou", "indicacao"],
    "data_cadastro": ["data_cadastro", "dt_cadastro", "data", "date", "cadastrado_em"],
}

FAIXA_LABELS = {(0,17):"≤17",(18,24):"18-24",(25,34):"25-34",
                (35,44):"35-44",(45,59):"45-59",(60,69):"60-69",(70,120):"70+"}

SCORE_FIDELIDADE = {"≤17":0.58,"18-24":0.61,"25-34":0.72,"35-44":0.72,
                    "45-59":0.78,"60-69":0.83,"70+":0.83,"":0.70}

MULTIPLICADOR_DENSIDADE = {
    "muito_alta":2.8,"alta":2.2,"media":1.9,"baixa":1.6,"":2.0
}

GENERO_MAP = {
    "m":"M","masculino":"M","male":"M","h":"M","homem":"M",
    "f":"F","feminino":"F","female":"F","mulher":"F",
}


def _detect_column(df: pd.DataFrame, field: str) -> str | None:
    aliases = COL_ALIASES.get(field, [field])
    for col in df.columns:
        if col.strip().lower().replace(" ","_") in aliases:
            return col
    return None


def _calc_faixa(idade) -> str:
    try:
        age = int(float(idade))
        for (lo, hi), label in FAIXA_LABELS.items():
            if lo <= age <= hi:
                return label
    except (ValueError, TypeError):
        pass
    return ""


def _parse_date(val) -> date | None:
    if pd.isna(val):
        return None
    s = str(val).strip()
    for fmt in ["%d/%m/%Y","%Y-%m-%d","%d-%m-%Y","%d/%m/%y"]:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


class CadastroIngestion:
    """Ingere planilha de eleitores, enriquece e persiste no banco"""

    def __init__(self, db: Session):
        self.db = db
        self._bairro_cache: Dict[str, BairroRef] = {}
        self._load_bairro_cache()

    def _load_bairro_cache(self):
        bairros = self.db.query(BairroRef).all()
        for b in bairros:
            self._bairro_cache[b.nome.lower()] = b
            # variantes sem acento simplificado
            self._bairro_cache[b.nome.lower().replace("ã","a").replace("â","a")
                               .replace("é","e").replace("ê","e").replace("ô","o")
                               .replace("ó","o").replace("ç","c").replace("í","i")] = b

    def _match_bairro(self, nome: str) -> BairroRef | None:
        key = nome.strip().lower()
        if key in self._bairro_cache:
            return self._bairro_cache[key]
        # fuzzy: bairro contém no nome
        for k, b in self._bairro_cache.items():
            if key in k or k in key:
                return b
        return None

    def ingest(self, df: pd.DataFrame, nome_arquivo: str, origem: str = "upload") -> Dict:
        col_map = {}
        for field in COL_ALIASES:
            found = _detect_column(df, field)
            if found:
                col_map[field] = found

        lote = LoteImportacao(
            nome_arquivo=nome_arquivo,
            total_registros=len(df),
            registros_validos=0,
            registros_duplicados=0,
            colunas_detectadas={f: c for f, c in col_map.items()},
            origem=origem,
        )
        self.db.add(lote)
        self.db.flush()

        validos = 0
        erros = []

        for idx, row in df.iterrows():
            try:
                nome = str(row[col_map["nome"]]).strip() if "nome" in col_map else f"Eleitor {idx}"
                bairro_raw = str(row[col_map["bairro"]]).strip() if "bairro" in col_map else ""
                bairro_ref = self._match_bairro(bairro_raw) if bairro_raw else None

                zona_raw = str(row[col_map["zona"]]).strip() if "zona" in col_map else ""
                zona_codigo = zona_raw.zfill(2) if zona_raw.isdigit() else (
                    bairro_ref.zona.codigo if bairro_ref and bairro_ref.zona else None
                )

                genero_raw = str(row[col_map["genero"]]).strip().lower() if "genero" in col_map else ""
                genero = GENERO_MAP.get(genero_raw, "")

                if "idade" in col_map:
                    idade_val = pd.to_numeric(row[col_map["idade"]], errors="coerce")
                    idade = int(idade_val) if not pd.isna(idade_val) else None
                elif "data_nascimento" in col_map:
                    dn = _parse_date(row[col_map["data_nascimento"]])
                    idade = (date.today() - dn).days // 365 if dn else None
                else:
                    idade = None

                faixa = _calc_faixa(idade) if idade else ""
                score_fid = SCORE_FIDELIDADE.get(faixa, 0.70)

                densidade = bairro_ref.densidade if bairro_ref else ""
                mult = MULTIPLICADOR_DENSIDADE.get(densidade, 2.0)

                classe = bairro_ref.classe_social if bairro_ref else None

                data_cad = _parse_date(row[col_map["data_cadastro"]]) if "data_cadastro" in col_map else None

                eleitor = Eleitor(
                    nome=nome,
                    bairro=bairro_raw or (bairro_ref.nome if bairro_ref else ""),
                    zona_codigo=zona_codigo,
                    genero=genero or None,
                    idade=idade,
                    faixa_etaria=faixa,
                    telefone=str(row[col_map["telefone"]]).strip() if "telefone" in col_map else None,
                    escolaridade=str(row[col_map["escolaridade"]]).strip() if "escolaridade" in col_map else None,
                    profissao=str(row[col_map["profissao"]]).strip() if "profissao" in col_map else None,
                    data_cadastro=data_cad,
                    origem_cadastro=str(row[col_map["origem"]]).strip() if "origem" in col_map else origem,
                    classe_social_estimada=classe,
                    score_fidelidade=score_fid,
                    multiplicador_influencia=mult,
                    lote_id=lote.id,
                )
                self.db.add(eleitor)
                validos += 1
            except Exception as e:
                erros.append({"linha": idx, "erro": str(e)})

        lote.registros_validos = validos
        self.db.commit()

        return {
            "lote_id": lote.id,
            "total": len(df),
            "validos": validos,
            "erros": len(erros),
            "colunas_detectadas": col_map,
        }


class SocialIngestion:
    """Ingere métricas de redes sociais"""

    def __init__(self, db: Session):
        self.db = db

    def ingest_metrica_diaria(self, data: Dict) -> MetricaRedeSocial:
        m = MetricaRedeSocial(
            data=_parse_date(data.get("data")) or date.today(),
            rede=data.get("rede", "instagram"),
            seguidores=int(data.get("seguidores", 0)),
            alcance_organico=int(data.get("alcance_organico", 0)),
            alcance_pago=int(data.get("alcance_pago", 0)),
            impressoes=int(data.get("impressoes", 0)),
            engajamento_total=int(data.get("engajamento_total", 0)),
            taxa_engajamento=float(data.get("taxa_engajamento", 0.0)),
            novos_seguidores=int(data.get("novos_seguidores", 0)),
            link_clicks=int(data.get("link_clicks", 0)),
            perfil_geografico=data.get("perfil_geografico"),
            perfil_demografico=data.get("perfil_demografico"),
        )
        self.db.add(m)
        self.db.commit()
        self.db.refresh(m)
        return m

    def ingest_post(self, data: Dict) -> PostRedeSocial:
        post = PostRedeSocial(
            rede=data.get("rede", "instagram"),
            data_post=datetime.now(),
            tipo=data.get("tipo", "foto"),
            tema=data.get("tema", ""),
            bairro_contexto=data.get("bairro_contexto"),
            alcance=int(data.get("alcance", 0)),
            impressoes=int(data.get("impressoes", 0)),
            likes=int(data.get("likes", 0)),
            comentarios=int(data.get("comentarios", 0)),
            compartilhamentos=int(data.get("compartilhamentos", 0)),
            salvamentos=int(data.get("salvamentos", 0)),
            cliques_perfil=int(data.get("cliques_perfil", 0)),
            conversao_cadastros=int(data.get("conversao_cadastros", 0)),
        )
        self.db.add(post)
        self.db.commit()
        self.db.refresh(post)
        return post


class EventoIngestion:
    """Ingere eventos de campanha e calcula ROI"""

    def __init__(self, db: Session):
        self.db = db

    def registrar_evento(self, data: Dict) -> EventoCampanha:
        publico = int(data.get("publico_estimado", 0))
        cadastros = int(data.get("cadastros_gerados", 0))
        custo = float(data.get("custo_estimado", 0.0))

        votos_est = cadastros * 0.67 * 0.715 * 2.2
        roi = votos_est / custo if custo > 0 else 0.0

        evento = EventoCampanha(
            nome=data.get("nome", "Evento"),
            tipo=data.get("tipo", "visita"),
            data_evento=_parse_date(data.get("data")) or date.today(),
            bairro=data.get("bairro", ""),
            zona_codigo=data.get("zona_codigo"),
            publico_estimado=publico,
            cadastros_gerados=cadastros,
            custo_estimado=custo,
            observacoes=data.get("observacoes"),
            votos_estimados_gerados=round(votos_est, 1),
            roi_votos_por_real=round(roi, 4),
        )
        self.db.add(evento)
        self.db.commit()
        self.db.refresh(evento)
        return evento
