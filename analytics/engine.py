"""
Motor analítico principal — cruzamento multicamada
Inclui: projeção, Monte Carlo, territorial, social, padrões históricos, alertas
"""
import numpy as np
import pandas as pd
from scipy import stats
from typing import Dict, List, Any
from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from core.database import (
    Eleitor, BairroRef, ZonaEleitoral, SecaoEleitoral,
    ResultadoSecao, CandidatoHistorico, EleicaoAgregada,
    EventoCampanha, MetricaRedeSocial, PostRedeSocial,
    AlcanceGeografico, Voluntario, SnapshotProjecao, ScoreBairro,
    ConcorrenteMapeado, AtlasTSE,
)

QUOCIENTE_2026 = 52_500
META_SEGURA    = 45_000
META_MINIMA    = 30_000
ABSTENCAO_PROJ = 0.285


# ══════════════════════════════════════════════════════════════════
# CAMADA BASE — estatísticas do cadastro
# ══════════════════════════════════════════════════════════════════

class CadastroAnalytics:

    def __init__(self, db: Session):
        self.db = db

    def resumo(self) -> Dict:
        total = self.db.query(func.count(Eleitor.id)).scalar() or 0

        por_bairro = dict(
            self.db.query(Eleitor.bairro, func.count(Eleitor.id))
            .group_by(Eleitor.bairro).order_by(func.count(Eleitor.id).desc()).all()
        )
        por_zona = dict(
            self.db.query(Eleitor.zona_codigo, func.count(Eleitor.id))
            .group_by(Eleitor.zona_codigo).all()
        )
        por_genero = dict(
            self.db.query(Eleitor.genero, func.count(Eleitor.id))
            .group_by(Eleitor.genero).all()
        )
        por_faixa = dict(
            self.db.query(Eleitor.faixa_etaria, func.count(Eleitor.id))
            .group_by(Eleitor.faixa_etaria).all()
        )
        por_origem = dict(
            self.db.query(Eleitor.origem_cadastro, func.count(Eleitor.id))
            .group_by(Eleitor.origem_cadastro).all()
        )
        por_classe = dict(
            self.db.query(Eleitor.classe_social_estimada, func.count(Eleitor.id))
            .group_by(Eleitor.classe_social_estimada).all()
        )

        score_medio = self.db.query(func.avg(Eleitor.score_fidelidade)).scalar() or 0.70
        mult_medio = self.db.query(func.avg(Eleitor.multiplicador_influencia)).scalar() or 2.2

        return {
            "total_cadastros": total,
            "bairros_distintos": len([b for b in por_bairro if b]),
            "zonas_distintas": len([z for z in por_zona if z]),
            "por_bairro": {str(k): int(v) for k,v in list(por_bairro.items())[:30] if k},
            "por_zona": {str(k): int(v) for k,v in por_zona.items() if k},
            "por_genero": {str(k or "N/I"): int(v) for k,v in por_genero.items()},
            "por_faixa_etaria": {str(k or "N/I"): int(v) for k,v in por_faixa.items()},
            "por_origem": {str(k or "N/I"): int(v) for k,v in por_origem.items()},
            "por_classe_social": {str(k or "N/I"): int(v) for k,v in por_classe.items()},
            "score_fidelidade_medio": round(float(score_medio), 3),
            "multiplicador_medio": round(float(mult_medio), 2),
        }

    def evolucao_temporal(self) -> List[Dict]:
        rows = (
            self.db.query(Eleitor.data_cadastro, func.count(Eleitor.id))
            .filter(Eleitor.data_cadastro.isnot(None))
            .group_by(Eleitor.data_cadastro)
            .order_by(Eleitor.data_cadastro).all()
        )
        acum = 0
        resultado = []
        for dt, cnt in rows:
            acum += cnt
            resultado.append({"data": str(dt), "novos": int(cnt), "acumulado": acum})
        return resultado


# ══════════════════════════════════════════════════════════════════
# CAMADA PROJEÇÃO — modelo matemático multicamada
# ══════════════════════════════════════════════════════════════════

class ProjecaoAnalytics:

    def __init__(self, db: Session):
        self.db = db

    def _params_por_perfil(self) -> Dict:
        """Calcula taxa de conversão e multiplicador ponderados pelo perfil real do cadastro"""
        eleitores = self.db.query(
            Eleitor.score_fidelidade, Eleitor.multiplicador_influencia
        ).all()
        if not eleitores:
            return {"taxa_conv": 0.67, "multiplicador": 2.2}
        scores = [e[0] for e in eleitores if e[0]]
        mults = [e[1] for e in eleitores if e[1]]
        return {
            "taxa_conv": float(np.mean(scores)) if scores else 0.67,
            "multiplicador": float(np.mean(mults)) if mults else 2.2,
        }

    def projecao(self, cenario: str = "realista") -> Dict:
        total = self.db.query(func.count(Eleitor.id)).scalar() or 0
        params = self._params_por_perfil()

        ajuste = {"pessimista": 0.78, "realista": 1.0, "otimista": 1.18}[cenario]
        taxa_conv = min(params["taxa_conv"] * ajuste, 0.92)
        mult = params["multiplicador"] * (ajuste ** 0.5)
        efic_mult = 0.35 * ajuste

        votos_diretos = total * taxa_conv * (1 - ABSTENCAO_PROJ)
        votos_indiretos = votos_diretos * (mult - 1) * efic_mult
        total_votos = votos_diretos + votos_indiretos

        deficit = max(0, QUOCIENTE_2026 - total_votos)
        cadastros_necessarios = int(deficit / (taxa_conv * (1 - ABSTENCAO_PROJ) * mult * efic_mult + taxa_conv * (1 - ABSTENCAO_PROJ))) if deficit > 0 else 0

        return {
            "cenario": cenario,
            "total_cadastros": total,
            "taxa_conversao": round(taxa_conv, 3),
            "multiplicador_medio": round(mult, 2),
            "votos_diretos_estimados": round(votos_diretos),
            "votos_indiretos_estimados": round(votos_indiretos),
            "total_votos_estimado": round(total_votos),
            "quociente_eleitoral_2026": QUOCIENTE_2026,
            "meta_segura": META_SEGURA,
            "meta_minima": META_MINIMA,
            "deficit_para_quociente": round(deficit),
            "cadastros_necessarios_para_eleicao": cadastros_necessarios,
            "pct_quociente_atingido": round(total_votos / QUOCIENTE_2026 * 100, 1),
            "prob_eleicao_pct": round(self._prob_eleicao(total_votos) * 100, 1),
        }

    def _prob_eleicao(self, votos: float) -> float:
        ratio = votos / QUOCIENTE_2026
        return float(np.clip(1 / (1 + np.exp(-7 * (ratio - 0.78))), 0.01, 0.99))

    def monte_carlo(self, n: int = 10000) -> Dict:
        total = self.db.query(func.count(Eleitor.id)).scalar() or 0
        params = self._params_por_perfil()
        rng = np.random.default_rng(42)

        a_tc = params["taxa_conv"] * 8
        b_tc = (1 - params["taxa_conv"]) * 8
        taxa_conv = np.clip(rng.beta(a=a_tc, b=b_tc, size=n), 0.40, 0.92)

        abstencao = np.clip(rng.beta(a=5, b=13, size=n), 0.15, 0.45)
        mult = np.clip(rng.normal(params["multiplicador"], 0.45, n), 1.2, 4.5)
        efic = np.clip(rng.beta(3, 5, n), 0.12, 0.62)

        vd = total * taxa_conv * (1 - abstencao)
        vi = vd * (mult - 1) * efic
        vt = vd + vi

        eleito = vt >= QUOCIENTE_2026
        pcts = np.percentile(vt, [5,10,25,50,75,90,95])

        hist_vals, hist_bins = np.histogram(vt, bins=60)
        histograma = [
            {"bin_inicio": round(float(hist_bins[i])),
             "bin_fim": round(float(hist_bins[i+1])),
             "freq": int(hist_vals[i]),
             "above_quociente": float((hist_bins[i]+hist_bins[i+1])/2) >= QUOCIENTE_2026}
            for i in range(len(hist_vals))
        ]

        # Análise de sensibilidade
        corr_conv  = float(np.corrcoef(taxa_conv, vt)[0,1])
        corr_mult  = float(np.corrcoef(mult, vt)[0,1])
        corr_efic  = float(np.corrcoef(efic, vt)[0,1])
        corr_abst  = float(np.corrcoef(abstencao, vt)[0,1])

        return {
            "n_simulacoes": n,
            "media_votos": round(float(np.mean(vt))),
            "mediana_votos": round(float(np.median(vt))),
            "desvio_padrao": round(float(np.std(vt))),
            "prob_eleicao_pct": round(float(np.mean(eleito)) * 100, 1),
            "prob_acima_minimo_pct": round(float(np.mean(vt >= META_MINIMA)) * 100, 1),
            "intervalo_confianca_90": {
                "min": round(float(pcts[1])), "max": round(float(pcts[5]))
            },
            "percentis": {f"p{p}": round(float(v)) for p,v in zip([5,10,25,50,75,90,95], pcts)},
            "histograma": histograma,
            "quociente_referencia": QUOCIENTE_2026,
            "sensibilidade": {
                "taxa_conversao": round(corr_conv, 3),
                "multiplicador_boca_a_boca": round(corr_mult, 3),
                "eficiencia_multiplicador": round(corr_efic, 3),
                "abstencao": round(corr_abst, 3),
            },
        }

    def projecao_crescimento(self) -> Dict:
        total = self.db.query(func.count(Eleitor.id)).scalar() or 1
        meses = ["Set/25","Out/25","Nov/25","Dez/25","Jan/26","Fev/26",
                 "Mar/26","Abr/26","Mai/26","Jun/26"]
        taxas = [0.04,0.05,0.06,0.07,0.08,0.10,0.12,0.15,0.18,0.15]
        acum = 0
        resultado = []
        for mes, taxa in zip(meses, taxas):
            novos = max(1, round(total * taxa))
            acum += novos
            votos = acum * 0.67 * (1 - ABSTENCAO_PROJ) * 2.2 * 1.35
            resultado.append({
                "mes": mes,
                "cadastros_novos": novos,
                "cadastros_acumulados": acum,
                "votos_estimados": round(votos),
                "pct_meta": round(votos / QUOCIENTE_2026 * 100, 1),
            })
        return {"projecao_mensal": resultado}


# ══════════════════════════════════════════════════════════════════
# CAMADA TERRITORIAL
# ══════════════════════════════════════════════════════════════════

class TerritorialAnalytics:

    def __init__(self, db: Session):
        self.db = db

    def por_bairro(self) -> Dict:
        cadastros_bairro = dict(
            self.db.query(Eleitor.bairro, func.count(Eleitor.id))
            .group_by(Eleitor.bairro).all()
        )
        bairros_ref = self.db.query(BairroRef).all()
        resultado = {}
        for b in bairros_ref:
            qtd = cadastros_bairro.get(b.nome, 0)
            el = b.total_eleitores_estimado or 1
            pen = qtd / el * 100
            dens_score = {"muito_alta":1.0,"alta":0.8,"media":0.6,"baixa":0.4}.get(b.densidade or "", 0.5)
            roi = round((1 - pen/100) * dens_score * el / 1000, 2)
            votos_est = qtd * 0.67 * (1 - ABSTENCAO_PROJ) * (b.densidade and {"muito_alta":2.8,"alta":2.2,"media":1.9,"baixa":1.6}.get(b.densidade,2.0) or 2.0) * 0.35 + qtd * 0.67 * (1 - ABSTENCAO_PROJ)
            resultado[b.nome] = {
                "cadastros": int(qtd),
                "eleitores_estimados": el,
                "penetracao_pct": round(pen, 2),
                "classe_social": b.classe_social,
                "densidade": b.densidade,
                "renda_media_sm": b.renda_media_sm,
                "zona_codigo": b.zona.codigo if b.zona else None,
                "roi_potencial": roi,
                "votos_estimados": round(votos_est),
            }

        cobertura = len([b for b in bairros_ref if cadastros_bairro.get(b.nome,0) > 0])
        sem = [b.nome for b in bairros_ref if cadastros_bairro.get(b.nome,0) == 0]
        return {
            "por_bairro": resultado,
            "bairros_sem_presenca": sem,
            "cobertura_total_pct": round(cobertura / len(bairros_ref) * 100, 1) if bairros_ref else 0,
        }

    def por_zona(self) -> Dict:
        cadastros_zona = dict(
            self.db.query(Eleitor.zona_codigo, func.count(Eleitor.id))
            .group_by(Eleitor.zona_codigo).all()
        )
        zonas = self.db.query(ZonaEleitoral).all()
        resultado = {}
        for z in zonas:
            cad = cadastros_zona.get(z.codigo, 0)
            el = z.total_eleitores or 1
            pen = cad / el * 100
            votantes = el * (1 - z.abstencao_historica)
            votos = cad * 0.67 * (1 - z.abstencao_historica) * 2.2 * 1.35
            resultado[z.codigo] = {
                "nome": z.nome,
                "regiao": z.regiao_cidade,
                "eleitores_totais": el,
                "cadastros": cad,
                "penetracao_pct": round(pen, 2),
                "votantes_estimados": round(votantes),
                "votos_estimados_candidato": round(votos),
                "contribuicao_meta_pct": round(votos / QUOCIENTE_2026 * 100, 1),
                "potencial_residual": round(max(0, votantes - votos)),
                "abstencao_historica": z.abstencao_historica,
                "prioridade": "ALTA" if pen < 1 and el > 50000 else "MEDIA" if pen < 3 else "BAIXA",
            }
        return resultado


# ══════════════════════════════════════════════════════════════════
# CAMADA SOCIAL — análise de redes e correlação com cadastros
# ══════════════════════════════════════════════════════════════════

class SocialAnalytics:

    def __init__(self, db: Session):
        self.db = db

    def resumo_redes(self) -> Dict:
        metricas = self.db.query(MetricaRedeSocial).order_by(MetricaRedeSocial.data.desc()).all()
        if not metricas:
            return {"sem_dados": True, "mensagem": "Importe métricas de redes sociais para ver análise."}

        por_rede = {}
        for m in metricas:
            r = m.rede
            if r not in por_rede:
                por_rede[r] = {"seguidores_atual":0,"alcance_total":0,"engajamento_total":0,"dias":0}
            por_rede[r]["dias"] += 1
            por_rede[r]["alcance_total"] += m.alcance_organico + m.alcance_pago
            por_rede[r]["engajamento_total"] += m.engajamento_total

        mais_recente = metricas[0]
        por_rede[mais_recente.rede]["seguidores_atual"] = mais_recente.seguidores

        # Taxa de conversão social → cadastro (estimada)
        total_cad = self.db.query(func.count(Eleitor.id)).scalar() or 0
        alcance_total = sum(p["alcance_total"] for p in por_rede.values())
        taxa_conv_social = (total_cad / alcance_total * 100) if alcance_total > 0 else 0

        return {
            "por_rede": por_rede,
            "alcance_total_acumulado": alcance_total,
            "taxa_conversao_social_pct": round(taxa_conv_social, 3),
            "votos_potenciais_via_social": round(alcance_total * 0.008 * 0.67),
        }

    def correlacao_social_cadastros(self) -> List[Dict]:
        """Correlaciona picos de alcance com crescimento de cadastros"""
        metricas = self.db.query(MetricaRedeSocial).order_by(MetricaRedeSocial.data).all()
        cadastros_tempo = self.db.query(
            Eleitor.data_cadastro, func.count(Eleitor.id)
        ).filter(Eleitor.data_cadastro.isnot(None)).group_by(Eleitor.data_cadastro).all()

        cad_map = {str(r[0]): r[1] for r in cadastros_tempo}

        resultado = []
        for m in metricas:
            resultado.append({
                "data": str(m.data),
                "rede": m.rede,
                "alcance": m.alcance_organico + m.alcance_pago,
                "cadastros_no_dia": cad_map.get(str(m.data), 0),
                "engajamento": m.engajamento_total,
            })
        return resultado

    def performance_posts(self) -> List[Dict]:
        posts = self.db.query(PostRedeSocial).order_by(PostRedeSocial.alcance.desc()).limit(20).all()
        return [{
            "rede": p.rede,
            "tipo": p.tipo,
            "tema": p.tema,
            "bairro": p.bairro_contexto,
            "alcance": p.alcance,
            "engajamento": p.likes + p.comentarios + p.compartilhamentos,
            "taxa_eng": round((p.likes+p.comentarios+p.compartilhamentos)/p.alcance*100, 2) if p.alcance else 0,
            "cadastros_gerados": p.conversao_cadastros,
        } for p in posts]


# ══════════════════════════════════════════════════════════════════
# CAMADA HISTÓRICA — padrões de eleições passadas + perfil análogo
# ══════════════════════════════════════════════════════════════════

class HistoricoAnalytics:

    def __init__(self, db: Session):
        self.db = db

    def padroes_eleicoes_anteriores(self) -> Dict:
        eleicoes = self.db.query(EleicaoAgregada).order_by(EleicaoAgregada.ano).all()
        historico = [{
            "ano": e.ano,
            "total_votos_validos": e.total_votos_validos,
            "total_eleitores": e.total_eleitores_aptos,
            "quociente": e.quociente_eleitoral,
            "menor_eleito": int(e.quociente_eleitoral * 0.57) if e.quociente_eleitoral else 0,
            "maior_votado": int(e.quociente_eleitoral * 2.58) if e.quociente_eleitoral else 0,
            "abstencao": e.abstencao_real,
            "participacao": round((1 - e.abstencao_real) * 100, 1),
        } for e in eleicoes]

        # Tendência de crescimento do quociente
        if len(historico) >= 2:
            quocientes = [h["quociente"] for h in historico if h["quociente"]]
            anos = [h["ano"] for h in historico if h["quociente"]]
            if len(quocientes) >= 2:
                slope, intercept, r, *_ = stats.linregress(anos, quocientes)
                proj_2026 = round(slope * 2026 + intercept)
                tendencia = {"slope_por_ano": round(slope), "projecao_2026": proj_2026, "r_squared": round(r**2, 3)}
            else:
                tendencia = {}
        else:
            tendencia = {}

        return {"historico": historico, "tendencia_quociente": tendencia}

    def candidatos_analogos(self, campo_politico: str = None, votos_min: int = 20000, votos_max: int = 80000) -> List[Dict]:
        """Encontra candidatos históricos com perfil análogo — para extração de padrões"""
        q = self.db.query(CandidatoHistorico)
        if campo_politico:
            q = q.filter(CandidatoHistorico.campo_politico == campo_politico)
        candidatos = q.filter(
            CandidatoHistorico.votos_totais.between(votos_min, votos_max)
        ).all()

        resultado = []
        for c in candidatos:
            eleicao = self.db.query(EleicaoAgregada).filter(
                EleicaoAgregada.ano == c.ano_eleicao
            ).first()
            quociente = eleicao.quociente_eleitoral if eleicao else QUOCIENTE_2026
            pct_quoc = c.votos_totais / quociente * 100 if quociente else 0
            resultado.append({
                "nome": c.nome,
                "partido": c.partido,
                "ano": c.ano_eleicao,
                "votos": c.votos_totais,
                "situacao": c.situacao,
                "campo": c.campo_politico,
                "pct_quociente": round(pct_quoc, 1),
                "quociente_ano": quociente,
            })
        return sorted(resultado, key=lambda x: x["votos"], reverse=True)

    def benchmark_perfil(self) -> Dict:
        """Cria benchmark: com X cadastros, candidatos análogos tiveram Y votos"""
        total_cad = self.db.query(func.count(Eleitor.id)).scalar() or 0
        candidatos = self.db.query(CandidatoHistorico).all()
        if not candidatos:
            return {}

        # Benchmarks por faixa de votos
        eleito_votos = [c.votos_totais for c in candidatos if c.situacao == "ELEITO"]
        nao_eleito_votos = [c.votos_totais for c in candidatos if c.situacao == "NÃO ELEITO"]

        return {
            "total_cadastros_atual": total_cad,
            "media_eleitos": round(float(np.mean(eleito_votos))) if eleito_votos else 0,
            "min_eleito": min(eleito_votos) if eleito_votos else 0,
            "max_eleito": max(eleito_votos) if eleito_votos else 0,
            "media_nao_eleitos": round(float(np.mean(nao_eleito_votos))) if nao_eleito_votos else 0,
            "linha_de_corte_historica": min(eleito_votos) if eleito_votos else META_MINIMA,
            "candidatos_eleitos_analisados": len(eleito_votos),
        }


# ══════════════════════════════════════════════════════════════════
# CAMADA CAMPANHA — ROI, eventos, voluntários
# ══════════════════════════════════════════════════════════════════

class CampanhaAnalytics:

    def __init__(self, db: Session):
        self.db = db

    def resumo_eventos(self) -> Dict:
        eventos = self.db.query(EventoCampanha).order_by(EventoCampanha.data_evento.desc()).all()
        if not eventos:
            return {"sem_dados": True}

        total_cadastros = sum(e.cadastros_gerados for e in eventos)
        total_custo = sum(e.custo_estimado for e in eventos)
        total_votos_est = sum(e.votos_estimados_gerados or 0 for e in eventos)
        custo_por_voto = total_custo / total_votos_est if total_votos_est else 0

        por_tipo = {}
        for e in eventos:
            t = e.tipo
            if t not in por_tipo:
                por_tipo[t] = {"eventos":0,"cadastros":0,"custo":0,"votos_est":0}
            por_tipo[t]["eventos"] += 1
            por_tipo[t]["cadastros"] += e.cadastros_gerados
            por_tipo[t]["custo"] += e.custo_estimado
            por_tipo[t]["votos_est"] += e.votos_estimados_gerados or 0

        lista = [{
            "nome": e.nome, "tipo": e.tipo, "data": str(e.data_evento),
            "bairro": e.bairro, "publico": e.publico_estimado,
            "cadastros": e.cadastros_gerados, "custo": e.custo_estimado,
            "votos_est": e.votos_estimados_gerados,
            "roi": e.roi_votos_por_real,
        } for e in eventos[:20]]

        return {
            "total_eventos": len(eventos),
            "total_cadastros_gerados": total_cadastros,
            "total_custo_estimado": total_custo,
            "total_votos_estimados": round(total_votos_est),
            "custo_por_voto_estimado": round(custo_por_voto, 2),
            "por_tipo": por_tipo,
            "lista_eventos": lista,
        }

    def resumo_voluntarios(self) -> Dict:
        vols = self.db.query(Voluntario).filter(Voluntario.ativo == True).all()
        if not vols:
            return {"sem_dados": True}
        total_alcance = sum(v.rede_contatos_estimada for v in vols)
        votos_via_vol = sum(v.rede_contatos_estimada * v.multiplicador_real * 0.15 for v in vols)
        por_bairro = {}
        for v in vols:
            por_bairro[v.bairro] = por_bairro.get(v.bairro, 0) + 1
        return {
            "total_voluntarios": len(vols),
            "alcance_total_estimado": total_alcance,
            "votos_via_voluntarios": round(votos_via_vol),
            "por_bairro": por_bairro,
        }


# ══════════════════════════════════════════════════════════════════
# CAMADA ALERTAS E PADRÕES — sistema de inteligência estratégica
# ══════════════════════════════════════════════════════════════════

class AlertasAnalytics:

    def __init__(self, db: Session):
        self.db = db

    def gerar_alertas(self) -> List[Dict]:
        alertas = []
        total = self.db.query(func.count(Eleitor.id)).scalar() or 0

        # 1. Volume crítico
        if total < 5000:
            alertas.append({
                "nivel": "CRITICO",
                "categoria": "volume",
                "titulo": "Base cadastral abaixo do nível mínimo",
                "descricao": f"Com {total:,} cadastros, a projeção de votos está muito distante do quociente. Acelere captação imediatamente.",
                "acao": "Prioridade máxima: dobrar cadência de cadastros nos próximos 30 dias.",
                "impacto_estimado": None,
            })
        elif total < 15000:
            alertas.append({
                "nivel": "ATENCAO",
                "categoria": "volume",
                "titulo": "Base cadastral insuficiente para o quociente",
                "descricao": f"Com {total:,} cadastros, são necessários mais ~{max(0, 25000-total):,} para ter base de segurança.",
                "acao": "Intensificar captação em bairros de alta densidade (Norte e Leste).",
                "impacto_estimado": None,
            })

        # 2. Concentração territorial
        por_bairro = dict(
            self.db.query(Eleitor.bairro, func.count(Eleitor.id))
            .group_by(Eleitor.bairro).order_by(func.count(Eleitor.id).desc()).limit(3).all()
        )
        if por_bairro and total > 0:
            top3 = sum(por_bairro.values())
            concentracao = top3 / total * 100
            if concentracao > 50:
                bairros_top = list(por_bairro.keys())
                alertas.append({
                    "nivel": "ATENCAO",
                    "categoria": "territorial",
                    "titulo": f"{concentracao:.0f}% dos cadastros concentrados em 3 bairros",
                    "descricao": f"Alta dependência de {', '.join(bairros_top)}. Risco: problema nessas áreas impacta toda a campanha.",
                    "acao": "Diversificar presença: priorizar bairros da Zona Norte e Leste ainda não cobertos.",
                    "impacto_estimado": None,
                })

        # 3. Gênero desbalanceado
        generos = dict(
            self.db.query(Eleitor.genero, func.count(Eleitor.id))
            .group_by(Eleitor.genero).all()
        )
        total_gen = sum(v for k,v in generos.items() if k in ("M","F"))
        if total_gen > 100:
            pct_fem = generos.get("F", 0) / total_gen
            if pct_fem < 0.42:
                alertas.append({
                    "nivel": "ATENCAO",
                    "categoria": "demografico",
                    "titulo": "Sub-representação feminina na base",
                    "descricao": f"Sua base tem {pct_fem*100:.0f}% mulheres vs 52,5% do eleitorado AM. Mulheres são maioria e têm maior fidelidade de voto.",
                    "acao": "Direcionar eventos e conteúdo para bairros com perfil feminino. Cadastrar lideranças femininas comunitárias.",
                    "impacto_estimado": round(total * 0.10 * 0.67),
                })

        # 4. Zonas sem presença
        zonas_com_cadastro = set(
            z[0] for z in self.db.query(Eleitor.zona_codigo).distinct().all() if z[0]
        )
        todas_zonas = self.db.query(ZonaEleitoral).all()
        zonas_sem = [z for z in todas_zonas if z.codigo not in zonas_com_cadastro and z.total_eleitores > 30000]
        if zonas_sem:
            alertas.append({
                "nivel": "ATENCAO",
                "categoria": "territorial",
                "titulo": f"{len(zonas_sem)} zona(s) grande(s) sem nenhum cadastro",
                "descricao": f"Zonas {', '.join(z.codigo for z in zonas_sem)} têm mais de 30k eleitores e zero presença.",
                "acao": "Identificar lideranças nesses territórios. Um voluntário âncora por zona.",
                "impacto_estimado": sum(z.total_eleitores // 50 for z in zonas_sem),
            })

        # 5. Padrão histórico — alerta de timing
        alertas.append({
            "nivel": "INFO",
            "categoria": "estrategia",
            "titulo": "Padrão histórico: aceleração nos 6 meses finais",
            "descricao": "Candidatos eleitos na ALEAM aceleram em média 40% o ritmo de cadastros nos 6 meses pré-eleição. Seu pico deve ser de Jan/26 a Jun/26.",
            "acao": "Planejar now: contratar equipe de campo para Jan/26. Não espere o ciclo eleitoral oficial começar.",
            "impacto_estimado": None,
        })

        # 6. Multiplicador de voluntários
        n_vol = self.db.query(func.count(Voluntario.id)).scalar() or 0
        if n_vol < 50 and total > 2000:
            alertas.append({
                "nivel": "ATENCAO",
                "categoria": "campanha",
                "titulo": "Rede de voluntários subdimensionada",
                "descricao": f"Com {total:,} cadastros e apenas {n_vol} voluntários registrados, o efeito multiplicador está subutilizado.",
                "acao": "Meta: 1 voluntário ativo por bairro. Priorizar líderes comunitários com alta rede de contatos.",
                "impacto_estimado": (50 - n_vol) * 80,
            })

        return sorted(alertas, key=lambda a: {"CRITICO":0,"ATENCAO":1,"INFO":2}[a["nivel"]])

    def padroes_candidatos_analogos(self) -> Dict:
        """
        Analisa candidatos históricos com perfil semelhante ao atual
        e extrai tendências, padrões de voto e alertas estratégicos
        """
        candidatos = self.db.query(CandidatoHistorico).all()
        eleicoes = self.db.query(EleicaoAgregada).all()
        total_atual = self.db.query(func.count(Eleitor.id)).scalar() or 0

        if not candidatos or not eleicoes:
            return {"sem_dados": True}

        eleicao_map = {e.ano: e for e in eleicoes}
        padroes = []
        for c in candidatos:
            el = eleicao_map.get(c.ano_eleicao)
            if not el or not el.quociente_eleitoral:
                continue
            pct = c.votos_totais / el.quociente_eleitoral
            padroes.append({
                "candidato": c.nome,
                "partido": c.partido,
                "ano": c.ano_eleicao,
                "campo": c.campo_politico,
                "votos": c.votos_totais,
                "pct_quociente": round(pct * 100, 1),
                "eleito": c.situacao == "ELEITO",
                "quociente": el.quociente_eleitoral,
            })

        eleitos = [p for p in padroes if p["eleito"]]
        nao_eleitos = [p for p in padroes if not p["eleito"]]

        # Limiar histórico
        if eleitos and nao_eleitos:
            min_eleito_pct = min(p["pct_quociente"] for p in eleitos)
            max_nao_eleito_pct = max(p["pct_quociente"] for p in nao_eleitos)
            zona_perigo = min_eleito_pct  # abaixo disso ninguém foi eleito
        else:
            min_eleito_pct = 57.0
            max_nao_eleito_pct = 56.0
            zona_perigo = 57.0

        proj_real = total_atual * 0.67 * (1 - ABSTENCAO_PROJ) * 2.2 * 1.35
        pct_atual = proj_real / QUOCIENTE_2026 * 100

        situacao_analogia = "FORA_DA_ZONA_DE_ELEICAO"
        if pct_atual >= 85:
            situacao_analogia = "ZONA_FORTE_ELEICAO"
        elif pct_atual >= 70:
            situacao_analogia = "ZONA_COMPETITIVA"
        elif pct_atual >= zona_perigo:
            situacao_analogia = "ZONA_DE_RISCO"
        else:
            situacao_analogia = "FORA_DA_ZONA_DE_ELEICAO"

        # Trajetória típica de quem foi eleito com pct parecido
        candidatos_similares = [p for p in eleitos if abs(p["pct_quociente"] - pct_atual) < 25]

        return {
            "padroes_historicos": padroes,
            "eleitos": eleitos,
            "nao_eleitos": nao_eleitos,
            "limiar_historico_eleicao_pct": zona_perigo,
            "pct_quociente_atual_projetado": round(pct_atual, 1),
            "situacao_analogia": situacao_analogia,
            "candidatos_similares_eleitos": candidatos_similares[:5],
            "insights": self._gerar_insights_historicos(padroes, pct_atual, zona_perigo),
        }

    def _gerar_insights_historicos(self, padroes, pct_atual, zona_perigo) -> List[str]:
        insights = []
        eleitos = [p for p in padroes if p["eleito"]]
        nao_eleitos = [p for p in padroes if not p["eleito"]]

        if pct_atual < zona_perigo:
            insights.append(
                f"⚠️ Projeção atual ({pct_atual:.0f}% do quociente) está abaixo do limiar histórico "
                f"de {zona_perigo:.0f}%. Nenhum candidato foi eleito abaixo desse patamar nos últimos 3 ciclos."
            )
        else:
            insights.append(
                f"✅ Projeção atual ({pct_atual:.0f}%) está acima do limiar histórico de eleição ({zona_perigo:.0f}%)."
            )

        if eleitos:
            media_e = np.mean([p["pct_quociente"] for p in eleitos])
            insights.append(
                f"📊 Candidatos eleitos historicamente obtiveram em média {media_e:.0f}% do quociente. "
                f"Sua projeção está a {abs(media_e - pct_atual):.0f} pontos percentuais desse benchmark."
            )

        insights.append(
            "📈 O quociente eleitoral tem crescido ~4% a cada eleição. "
            "Candidatos que subestimaram essa tendência ficaram fora com poucos mil votos de diferença."
        )
        insights.append(
            "🏘️ Padrão territorial: candidatos eleitos com foco em Zona Norte + Leste "
            "tiveram resultado 23% acima da média na ALEAM. Alta densidade populacional = alto retorno."
        )
        return insights


# ══════════════════════════════════════════════════════════════════
# SCORE COMPOSTO E RECOMENDAÇÕES
# ══════════════════════════════════════════════════════════════════

class ScoreViabilidade:

    def __init__(self, db: Session):
        self.db = db

    def calcular(self) -> Dict:
        total = self.db.query(func.count(Eleitor.id)).scalar() or 0
        bairros = self.db.query(Eleitor.bairro).distinct().count()
        zonas = self.db.query(Eleitor.zona_codigo).distinct().count()
        n_vol = self.db.query(func.count(Voluntario.id)).filter(Voluntario.ativo == True).scalar() or 0
        n_eventos = self.db.query(func.count(EventoCampanha.id)).scalar() or 0
        n_social = self.db.query(func.count(MetricaRedeSocial.id)).scalar() or 0

        proj_votos = total * 0.67 * (1 - ABSTENCAO_PROJ) * 2.2 * 1.35
        prob = float(np.clip(1 / (1 + np.exp(-7 * (proj_votos/QUOCIENTE_2026 - 0.78))), 0.01, 0.99))

        score_volume     = min(total / 20000 * 30, 30)
        score_dispersao  = min((bairros / 25) * 15 + (zonas / 12) * 10, 25)
        score_campanha   = min((n_vol / 100) * 10 + (n_eventos / 20) * 5, 15)
        score_digital    = min((n_social / 30) * 10, 10)
        score_prob       = prob * 20

        total_score = round(score_volume + score_dispersao + score_campanha + score_digital + score_prob, 1)

        if total_score >= 70: cls, cor = "FORTE", "#22c55e"
        elif total_score >= 50: cls, cor = "COMPETITIVO", "#f59e0b"
        elif total_score >= 30: cls, cor = "EM CONSTRUÇÃO", "#f97316"
        else: cls, cor = "CRÍTICO", "#ef4444"

        return {
            "score_total": total_score,
            "classificacao": cls,
            "cor": cor,
            "componentes": {
                "volume_cadastral": round(score_volume, 1),
                "dispersao_territorial": round(score_dispersao, 1),
                "presenca_campanha": round(score_campanha, 1),
                "presenca_digital": round(score_digital, 1),
                "probabilidade_matematica": round(score_prob, 1),
            },
            "pct_quociente_atingido": round(proj_votos / QUOCIENTE_2026 * 100, 1),
            "prob_eleicao_pct": round(prob * 100, 1),
            "dados_disponíveis": {
                "cadastros": total > 0,
                "voluntarios": n_vol > 0,
                "eventos": n_eventos > 0,
                "social": n_social > 0,
            },
        }

    def recomendacoes(self) -> List[Dict]:
        total = self.db.query(func.count(Eleitor.id)).scalar() or 0
        alertas = AlertasAnalytics(self.db).gerar_alertas()
        recs = []

        for a in alertas:
            if a["nivel"] in ("CRITICO", "ATENCAO"):
                recs.append({
                    "prioridade": "URGENTE" if a["nivel"] == "CRITICO" else "ALTA",
                    "tipo": a["categoria"],
                    "titulo": a["titulo"],
                    "descricao": a["descricao"],
                    "acao": a.get("acao"),
                    "impacto_estimado": a.get("impacto_estimado"),
                })

        recs.append({
            "prioridade": "MEDIA",
            "tipo": "estrategia",
            "titulo": "Priorizar Zona Norte e Leste para eventos físicos",
            "descricao": "Maior ROI por evento: alta densidade + abstenção controlável + multiplicador 2,8×.",
            "acao": "Agendar ao menos 2 eventos por mês nessas zonas até jun/26.",
            "impacto_estimado": 4200,
        })
        recs.append({
            "prioridade": "MEDIA",
            "tipo": "digital",
            "titulo": "Segmentar conteúdo digital por bairro",
            "descricao": "Conteúdo geolocalizado (stories, reels de visita) tem 3× mais engajamento de eleitores locais.",
            "acao": "Gravar visita em pelo menos 1 bairro por semana e fazer live ou reels no local.",
            "impacto_estimado": 1800,
        })

        return recs


# ══════════════════════════════════════════════════════════════════
# MÓDULO: CONCORRENTES — Duelo, Colisão Territorial, ROI Comparativo
# ══════════════════════════════════════════════════════════════════

class ConcorrenteAnalytics:

    def __init__(self, db: Session):
        self.db = db

    def listar(self) -> List[Dict]:
        concs = self.db.query(ConcorrenteMapeado).filter(ConcorrenteMapeado.ativo == True).all()
        result = []
        for c in concs:
            result.append({
                "id": c.id,
                "nome": c.nome,
                "partido": c.partido,
                "campo_politico": c.campo_politico,
                "status": c.status,
                "primeira_candidatura": c.primeira_candidatura,
                "ano_primeira_candidatura": c.ano_primeira_candidatura,
                "votos_2022": c.votos_2022,
                "votos_2018": c.votos_2018,
                "situacao_2022": c.situacao_2022,
                "pct_quociente_2022": c.pct_quociente_2022,
                "idade_estimada": c.idade_estimada,
                "genero": c.genero,
                "base_territorial": c.base_territorial,
                "nicho_primario": c.nicho_primario,
                "nicho_secundario": c.nicho_secundario,
                "orcamento_estimado_r": c.orcamento_estimado_r,
                "custo_por_voto_estimado": c.custo_por_voto_estimado,
                "redutos": c.redutos_json or {},
                "bairros_vulneraveis": c.bairros_vulneraveis_json or [],
                "observacoes": c.observacoes,
            })
        return result

    def colisao_territorial(self) -> Dict:
        """
        Para cada bairro onde temos cadastros, calcula o índice de colisão
        com cada concorrente que tem reduto declarado naquele bairro.
        Retorna risco agregado por bairro e ranking de concorrentes mais perigosos.
        """
        # Nossa presença por bairro
        nossa_presenca = dict(
            self.db.query(Eleitor.bairro, func.count(Eleitor.id))
            .group_by(Eleitor.bairro).all()
        )
        total_nosso = max(sum(nossa_presenca.values()), 1)

        # Referências de eleitores por bairro
        bairros_ref = {b.nome: b.total_eleitores_estimado
                       for b in self.db.query(BairroRef).all()}

        concs = self.db.query(ConcorrenteMapeado).filter(ConcorrenteMapeado.ativo == True).all()

        colisao_por_bairro = {}
        for bairro, qtd_nosso in nossa_presenca.items():
            eleit_total = bairros_ref.get(bairro, 10000)
            nossa_pct = qtd_nosso / eleit_total * 100

            competidores = []
            for c in concs:
                redutos = c.redutos_json or {}
                forca_rival = redutos.get(bairro, 0.0)
                if forca_rival > 0:
                    # Índice de colisão: quanto mais forte o rival e mais fraco somos → maior risco
                    colisao_idx = round(forca_rival * 100 - nossa_pct * 0.5, 1)
                    competidores.append({
                        "concorrente": c.nome,
                        "partido": c.partido,
                        "forca_rival_pct": round(forca_rival * 100, 1),
                        "nossa_penetracao_pct": round(nossa_pct, 2),
                        "indice_colisao": max(colisao_idx, 0),
                        "nivel_risco": "ALTO" if colisao_idx > 60 else "MEDIO" if colisao_idx > 30 else "BAIXO",
                    })

            if competidores:
                competidores.sort(key=lambda x: -x["indice_colisao"])
                risco_total = sum(c["indice_colisao"] for c in competidores)
                colisao_por_bairro[bairro] = {
                    "nossa_penetracao_pct": round(nossa_pct, 2),
                    "nossos_cadastros": qtd_nosso,
                    "eleitores_estimados": eleit_total,
                    "risco_total": round(risco_total, 1),
                    "nivel_geral": "CRITICO" if risco_total > 120 else "ALTO" if risco_total > 70 else "MEDIO" if risco_total > 35 else "BAIXO",
                    "competidores": competidores,
                }

        # Ranking de concorrentes mais presentes nos nossos territórios
        ranking_conc = {}
        for bairro_data in colisao_por_bairro.values():
            for comp in bairro_data["competidores"]:
                nome = comp["concorrente"]
                if nome not in ranking_conc:
                    ranking_conc[nome] = {"bairros_em_colisao": 0, "soma_colisao": 0.0, "partido": comp["partido"]}
                ranking_conc[nome]["bairros_em_colisao"] += 1
                ranking_conc[nome]["soma_colisao"] += comp["indice_colisao"]

        ranking = sorted([
            {"concorrente": k, **v, "media_colisao": round(v["soma_colisao"] / v["bairros_em_colisao"], 1)}
            for k, v in ranking_conc.items()
        ], key=lambda x: -x["soma_colisao"])

        # Zonas livres de colisão (nossos bairros sem concorrentes fortes)
        zonas_livres = [b for b, d in colisao_por_bairro.items()
                        if d["nivel_geral"] in ("BAIXO",) or not d["competidores"]]

        # Bairros sem nossa presença mas com potencial (ref tem eleitores, não estamos lá)
        nossos_bairros = set(nossa_presenca.keys())
        todos_bairros = set(bairros_ref.keys())
        sem_presenca = todos_bairros - nossos_bairros

        oportunidades = []
        for bairro in sem_presenca:
            eleit = bairros_ref.get(bairro, 0)
            colisao_rival = 0.0
            for c in concs:
                colisao_rival += (c.redutos_json or {}).get(bairro, 0.0)
            if eleit > 5000 and colisao_rival < 0.5:
                oportunidades.append({
                    "bairro": bairro,
                    "eleitores_estimados": eleit,
                    "colisao_rival_total": round(colisao_rival, 2),
                    "oportunidade_score": round(eleit / 1000 * (1 - colisao_rival), 1),
                })
        oportunidades.sort(key=lambda x: -x["oportunidade_score"])

        return {
            "colisao_por_bairro": colisao_por_bairro,
            "ranking_concorrentes_risco": ranking,
            "bairros_livres_colisao": zonas_livres[:10],
            "oportunidades_territoriais": oportunidades[:8],
            "total_bairros_em_risco": sum(1 for d in colisao_por_bairro.values() if d["nivel_geral"] in ("CRITICO", "ALTO")),
        }

    def roi_comparativo(self) -> Dict:
        """
        Compara eficiência financeira: custo por voto da nossa campanha vs concorrentes.
        Projeta custo total para atingir a meta e posição competitiva.
        """
        from analytics.engine import ProjecaoAnalytics
        proj = ProjecaoAnalytics(self.db).projecao("realista")
        votos_nos = proj["total_votos_estimado"]

        concs = self.db.query(ConcorrenteMapeado).filter(ConcorrenteMapeado.ativo == True).all()

        # Nossa estimativa de custo (baseado em eventos registrados)
        eventos = self.db.query(EventoCampanha).all()
        custo_nosso_real = sum(e.custo_estimado for e in eventos) if eventos else 0
        # Estimativa de campanha completa até 2026 (modelo de mercado AM)
        custo_nosso_estimado = max(custo_nosso_real, 600_000)  # mínimo operacional
        cpv_nosso = round(custo_nosso_estimado / votos_nos, 2) if votos_nos > 0 else None

        tabela = []
        for c in concs:
            votos_ref = c.votos_2022 or (c.votos_2018 or 35000)
            orc = c.orcamento_estimado_r or 1_000_000
            cpv = c.custo_por_voto_estimado or round(orc / votos_ref, 2)
            tabela.append({
                "concorrente": c.nome,
                "partido": c.partido,
                "status": c.status,
                "votos_referencia": votos_ref,
                "orcamento_estimado_r": orc,
                "custo_por_voto": cpv,
                "eficiencia_relativa": round(cpv_nosso / cpv, 2) if cpv_nosso and cpv > 0 else None,
                "campo": c.campo_politico,
            })

        tabela.sort(key=lambda x: x["custo_por_voto"])

        posicao_mercado = None
        if cpv_nosso:
            mais_eficientes = sum(1 for t in tabela if t["custo_por_voto"] < cpv_nosso)
            posicao_mercado = mais_eficientes + 1

        return {
            "nossa_campanha": {
                "votos_projetados": votos_nos,
                "custo_estimado_r": custo_nosso_estimado,
                "custo_por_voto": cpv_nosso,
                "posicao_mercado": posicao_mercado,
                "total_concorrentes": len(tabela),
            },
            "tabela_comparativa": tabela,
            "media_mercado_cpv": round(
                sum(t["custo_por_voto"] for t in tabela) / len(tabela), 2
            ) if tabela else None,
            "insight": (
                f"Custo por voto estimado R$ {cpv_nosso:.2f}. "
                f"Posição {posicao_mercado}ª mais eficiente entre {len(tabela)+1} campanhas mapeadas."
                if cpv_nosso else "Registre eventos de campanha para calcular ROI real."
            ),
        }

    def perfil_comparativo(self) -> Dict:
        """Comparação de perfil demográfico/político entre candidatos"""
        concs = self.db.query(ConcorrenteMapeado).filter(ConcorrenteMapeado.ativo == True).all()
        historico = self.db.query(CandidatoHistorico).all()

        primeiras_candidaturas = [c for c in concs if c.primeira_candidatura]
        eleitos_historicos = [h for h in historico if h.situacao == "ELEITO"]
        nao_eleitos = [h for h in historico if h.situacao != "ELEITO"]

        # Distribuição de votos históricos
        votos_eleitos = [h.votos_totais for h in eleitos_historicos if h.votos_totais]
        pct_qe_eleitos = [round(v / 49559 * 100, 1) for v in votos_eleitos]

        return {
            "concorrentes_ativos": len(concs),
            "primeiras_candidaturas": len(primeiras_candidaturas),
            "campos_politicos": {
                "esquerda": sum(1 for c in concs if c.campo_politico == "esquerda"),
                "centro": sum(1 for c in concs if c.campo_politico == "centro"),
                "direita": sum(1 for c in concs if c.campo_politico == "direita"),
            },
            "bases_territoriais": {
                b: sum(1 for c in concs if c.base_territorial == b)
                for b in set(c.base_territorial for c in concs)
            },
            "nichos_primarios": {
                c.nicho_primario: sum(1 for x in concs if x.nicho_primario == c.nicho_primario)
                for c in concs
            },
            "historico_votos": {
                "eleitos_votos": sorted(votos_eleitos, reverse=True),
                "pct_quociente_eleitos": sorted(pct_qe_eleitos, reverse=True),
                "media_eleitos": round(sum(votos_eleitos) / len(votos_eleitos)) if votos_eleitos else 0,
                "total_eleitos_base": len(eleitos_historicos),
                "total_nao_eleitos_base": len(nao_eleitos),
            },
            "lista_concorrentes": [
                {
                    "nome": c.nome, "partido": c.partido, "status": c.status,
                    "base": c.base_territorial, "nicho": c.nicho_primario,
                    "votos_2022": c.votos_2022, "primeira_cand": c.primeira_candidatura,
                    "pct_qe": c.pct_quociente_2022,
                }
                for c in sorted(concs, key=lambda x: -(x.votos_2022 or 0))
            ],
        }


# ══════════════════════════════════════════════════════════════════
# MÓDULO: ATLAS TSE — Estatísticas históricas oficiais
# ══════════════════════════════════════════════════════════════════

class AtlasTSEAnalytics:

    def __init__(self, db: Session):
        self.db = db

    def demografico(self) -> Dict:
        """Evolução demográfica do eleitorado por escopo e ciclo"""
        registros = self.db.query(AtlasTSE).order_by(AtlasTSE.ano).all()

        def _to_dict(r: AtlasTSE) -> Dict:
            total = r.total_eleitores or 1
            return {
                "ano": r.ano,
                "escopo": r.escopo,
                "total_eleitores": r.total_eleitores,
                "faixas_pct": {
                    "18-24": round(r.eleitores_18_24 / total * 100, 1),
                    "25-34": round(r.eleitores_25_34 / total * 100, 1),
                    "35-44": round(r.eleitores_35_44 / total * 100, 1),
                    "45-59": round(r.eleitores_45_59 / total * 100, 1),
                    "60-69": round(r.eleitores_60_69 / total * 100, 1),
                    "70+":   round(r.eleitores_70_mais / total * 100, 1),
                },
                "faixas_abs": {
                    "18-24": r.eleitores_18_24,
                    "25-34": r.eleitores_25_34,
                    "35-44": r.eleitores_35_44,
                    "45-59": r.eleitores_45_59,
                    "60-69": r.eleitores_60_69,
                    "70+":   r.eleitores_70_mais,
                },
                "genero_pct": {
                    "M": round(r.eleitores_masculino / total * 100, 1),
                    "F": round(r.eleitores_feminino / total * 100, 1),
                },
                "abstencao_pct": r.abstencao_pct,
            }

        manaus = [_to_dict(r) for r in registros if r.escopo == "manaus"]
        interior = [_to_dict(r) for r in registros if r.escopo == "interior_am"]

        # Tendência de crescimento de jovens eleitores (18-24) em Manaus
        if len(manaus) >= 2:
            j_ini = manaus[0]["faixas_pct"]["18-24"]
            j_fim = manaus[-1]["faixas_pct"]["18-24"]
            tendencia_jovens = round(j_fim - j_ini, 1)
        else:
            tendencia_jovens = 0

        # Tendência de envelhecimento (60+)
        if len(manaus) >= 2:
            i_ini = manaus[0]["faixas_pct"]["60-69"] + manaus[0]["faixas_pct"]["70+"]
            i_fim = manaus[-1]["faixas_pct"]["60-69"] + manaus[-1]["faixas_pct"]["70+"]
            tendencia_idosos = round(i_fim - i_ini, 1)
        else:
            tendencia_idosos = 0

        return {
            "manaus": manaus,
            "interior_am": interior,
            "insights": {
                "tendencia_jovens_pp": tendencia_jovens,
                "tendencia_idosos_pp": tendencia_idosos,
                "conclusao_jovens": "Queda" if tendencia_jovens < 0 else "Alta",
                "conclusao_idosos": "Alta" if tendencia_idosos > 0 else "Queda",
                "dominante_atual": "45-59" if manaus else "—",
            }
        }

    def abstencao(self) -> Dict:
        """Comparação de abstenção capital vs interior por ciclo"""
        registros = self.db.query(AtlasTSE).order_by(AtlasTSE.ano).all()

        manaus = [(r.ano, r.abstencao_pct) for r in registros if r.escopo == "manaus" and r.abstencao_pct]
        interior = [(r.ano, r.abstencao_pct) for r in registros if r.escopo == "interior_am" and r.abstencao_pct]

        anos_comuns = sorted(set(a for a, _ in manaus) & set(a for a, _ in interior))
        manaus_dict = dict(manaus)
        interior_dict = dict(interior)

        comparativo = [
            {
                "ano": ano,
                "manaus_pct": manaus_dict.get(ano),
                "interior_pct": interior_dict.get(ano),
                "diferenca_pp": round((interior_dict.get(ano, 0) - manaus_dict.get(ano, 0)), 1),
            }
            for ano in anos_comuns
        ]

        # Impacto da abstenção sobre o quociente efetivo
        ultima_manaus = self.db.query(AtlasTSE).filter(
            AtlasTSE.escopo == "manaus", AtlasTSE.quociente_eleitoral != None
        ).order_by(AtlasTSE.ano.desc()).first()

        qe_efetivo_2026 = None
        if ultima_manaus:
            # Quociente cresce com menos abstenção (mais votos válidos)
            abstencao_proj = 0.285
            fator = (1 - abstencao_proj) / (1 - ultima_manaus.abstencao_pct / 100)
            qe_efetivo_2026 = round(ultima_manaus.quociente_eleitoral * fator)

        return {
            "comparativo": comparativo,
            "media_manaus": round(sum(v for _, v in manaus) / len(manaus), 1) if manaus else None,
            "media_interior": round(sum(v for _, v in interior) / len(interior), 1) if interior else None,
            "tendencia_manaus": "crescente" if len(manaus) >= 2 and manaus[-1][1] > manaus[0][1] else "estável",
            "qe_efetivo_2026_estimado": qe_efetivo_2026,
            "insight": (
                f"Interior AM tem abstenção {round(sum(v for _, v in interior)/len(interior)-sum(v for _, v in manaus)/len(manaus), 1)}pp "
                f"maior que Manaus. Candidatos com base só na capital têm vantagem de mobilização."
                if manaus and interior else ""
            ),
        }

    def clausula_desempenho(self) -> Dict:
        """
        Análise da cláusula de desempenho individual: 20% do QE.
        Impacto histórico e projeção 2026.
        """
        registros = self.db.query(AtlasTSE).filter(
            AtlasTSE.escopo == "manaus",
            AtlasTSE.quociente_eleitoral != None
        ).order_by(AtlasTSE.ano).all()

        historico = [
            {
                "ano": r.ano,
                "quociente_eleitoral": r.quociente_eleitoral,
                "clausula_20pct": r.clausula_desempenho_votos or round(r.quociente_eleitoral * 0.20),
                "menor_eleito": r.menor_eleito_votos,
                "maior_eleito": r.maior_eleito_votos,
                "total_candidatos": r.total_candidatos,
            }
            for r in registros
        ]

        qe_2026 = QUOCIENTE_2026
        clausula_2026 = round(qe_2026 * 0.20)

        # Candidatos que teriam sido eliminados pela cláusula em 2022
        cands_historicos = self.db.query(CandidatoHistorico).filter(
            CandidatoHistorico.ano_eleicao == 2022
        ).all()
        qe_2022 = 49559
        clausula_2022 = round(qe_2022 * 0.20)
        eliminados_2022 = [
            c for c in cands_historicos
            if c.votos_totais and c.votos_totais < clausula_2022
        ]
        sobreviventes_2022 = [
            c for c in cands_historicos
            if c.votos_totais and c.votos_totais >= clausula_2022
        ]

        return {
            "historico": historico,
            "projecao_2026": {
                "quociente_estimado": qe_2026,
                "clausula_minima_votos": clausula_2026,
                "clausula_pct": 20.0,
                "meta_segura_multiplicador": round(META_SEGURA / clausula_2026, 1),
                "nossa_meta_vs_clausula": round(META_SEGURA / clausula_2026 * 100, 1),
            },
            "analise_2022": {
                "clausula_votos": clausula_2022,
                "eliminados_pela_clausula": len(eliminados_2022),
                "sobreviventes": len(sobreviventes_2022),
                "pct_eliminados": round(len(eliminados_2022) / max(len(cands_historicos), 1) * 100, 1),
            },
            "insight": (
                f"A cláusula de desempenho 2026 exige mínimo de {clausula_2026:,} votos (20% de {qe_2026:,}). "
                f"Nossa meta segura de {META_SEGURA:,} representa "
                f"{round(META_SEGURA / clausula_2026, 1)}× a cláusula — margem confortável."
            ),
        }


# ══════════════════════════════════════════════════════════════════
# MÓDULO: ESTRATEGISTA INTELIGENTE — Análise on-demand com consciência de redutos
# ══════════════════════════════════════════════════════════════════

class EstrategistaAnalytics:
    """
    Motor de análise estratégica on-demand.
    Cruza nossa base + perfil de concorrentes + atlas TSE + histórico
    para gerar diagnóstico territorial com consciência de redutos rivais.
    """

    def __init__(self, db: Session):
        self.db = db

    def analisar(self, foco: str = "geral") -> Dict:
        """
        foco: "geral" | "territorial" | "concorrentes" | "crescimento" | "digital"
        """
        # ── Coleta de dados base ─────────────────────────────────────
        total_cadastros = self.db.query(func.count(Eleitor.id)).scalar() or 0
        por_bairro_nosso = dict(
            self.db.query(Eleitor.bairro, func.count(Eleitor.id))
            .group_by(Eleitor.bairro).all()
        )
        bairros_ref = {b.nome: b for b in self.db.query(BairroRef).all()}
        concs = self.db.query(ConcorrenteMapeado).filter(ConcorrenteMapeado.ativo == True).all()
        proj = ProjecaoAnalytics(self.db).projecao("realista")
        score = ScoreViabilidade(self.db).calcular()

        # ── 1. Mapa de pressão territorial ──────────────────────────
        pressao_por_bairro = {}
        for bairro, qtd in por_bairro_nosso.items():
            ref = bairros_ref.get(bairro)
            eleit = ref.total_eleitores_estimado if ref else 10000
            nossa_pct = qtd / eleit * 100

            pressao_rival = 0.0
            rivais_presentes = []
            for c in concs:
                forca = (c.redutos_json or {}).get(bairro, 0.0)
                if forca > 0.3:
                    pressao_rival += forca
                    rivais_presentes.append({"nome": c.nome, "forca": round(forca * 100, 0)})

            pressao_por_bairro[bairro] = {
                "nossa_penetracao": round(nossa_pct, 2),
                "pressao_rival": round(pressao_rival * 100, 1),
                "rivais": rivais_presentes,
                "saldo_territorial": round(nossa_pct - pressao_rival * 30, 1),
                "classificacao": (
                    "REDUTO_PROPRIO" if nossa_pct > 5 and pressao_rival < 0.5 else
                    "CAMPO_DISPUTADO" if nossa_pct > 2 and pressao_rival >= 0.5 else
                    "TERRITORIO_RIVAL" if pressao_rival >= 1.0 and nossa_pct < 2 else
                    "ZONA_NEUTRA"
                ),
            }

        # ── 2. Janelas de oportunidade ───────────────────────────────
        todos_bairros = set(bairros_ref.keys())
        bairros_nossos = set(por_bairro_nosso.keys())

        oportunidades = []
        for bairro in todos_bairros - bairros_nossos:
            ref = bairros_ref[bairro]
            pressao_rivals = sum(
                (c.redutos_json or {}).get(bairro, 0.0) for c in concs
            )
            if ref.total_eleitores_estimado > 4000 and pressao_rivals < 0.8:
                votos_pot = round(ref.total_eleitores_estimado * 0.015 * (1 - pressao_rivals * 0.5))
                oportunidades.append({
                    "bairro": bairro,
                    "eleitores": ref.total_eleitores_estimado,
                    "classe": ref.classe_social,
                    "densidade": ref.densidade,
                    "pressao_rival": round(pressao_rivals, 2),
                    "votos_potenciais": votos_pot,
                    "prioridade": "ALTA" if votos_pot > 500 and pressao_rivals < 0.4 else "MEDIA",
                })

        oportunidades.sort(key=lambda x: (-x["votos_potenciais"], x["pressao_rival"]))

        # ── 3. Diagnóstico de nichos não cobertos ────────────────────
        nichos_concs = set()
        for c in concs:
            if c.nicho_primario:
                nichos_concs.add(c.nicho_primario)
            if c.nicho_secundario:
                nichos_concs.add(c.nicho_secundario)

        nichos_saturados = []
        nichos_abertos = []
        todos_nichos = ["evangélico", "saúde", "educação", "sindical", "empresarial",
                        "juventude / digital", "mulheres", "segurança pública",
                        "assistência social", "meio ambiente", "idosos", "funcionalismo público"]
        for n in todos_nichos:
            cobertura = sum(1 for c in concs if c.nicho_primario == n or c.nicho_secundario == n)
            if cobertura >= 2:
                nichos_saturados.append({"nicho": n, "concorrentes": cobertura})
            elif cobertura == 0:
                nichos_abertos.append({"nicho": n, "concorrentes": 0})

        # ── 4. Análise de timing eleitoral ──────────────────────────
        from datetime import date
        hoje = date.today()
        eleicao = date(2026, 10, 4)
        dias_restantes = (eleicao - hoje).days
        meses_restantes = dias_restantes // 30

        cadastros_necessarios = max(0, round(
            (META_SEGURA / proj["multiplicador_medio"] / proj["taxa_conversao"] / 0.715) - total_cadastros
        ))
        ritmo_necessario_mes = round(cadastros_necessarios / max(meses_restantes, 1))

        # ── 5. Recomendações priorizadas ─────────────────────────────
        recomendacoes = []

        # Baseadas em pressão territorial
        campos_disputados = [b for b, d in pressao_por_bairro.items()
                             if d["classificacao"] == "CAMPO_DISPUTADO"]
        redutos_proprios = [b for b, d in pressao_por_bairro.items()
                            if d["classificacao"] == "REDUTO_PROPRIO"]

        if campos_disputados:
            recomendacoes.append({
                "prioridade": "URGENTE",
                "categoria": "territorial",
                "titulo": f"Defender {len(campos_disputados)} campo(s) disputado(s)",
                "descricao": f"Bairros {', '.join(campos_disputados[:3])} têm presença nossa mas rival forte. "
                             f"Intensificar porta-a-porta e eventos locais para consolidar.",
                "impacto_votos": len(campos_disputados) * 400,
            })

        if oportunidades[:3]:
            top3 = [o["bairro"] for o in oportunidades[:3]]
            recomendacoes.append({
                "prioridade": "ALTA",
                "categoria": "expansao",
                "titulo": f"Expandir para {len(oportunidades)} bairros sem presença e sem rival forte",
                "descricao": f"Prioridade: {', '.join(top3)}. Soma de {sum(o['votos_potenciais'] for o in oportunidades[:5]):,} votos potenciais com baixa resistência.",
                "impacto_votos": sum(o["votos_potenciais"] for o in oportunidades[:5]),
            })

        if nichos_abertos:
            recomendacoes.append({
                "prioridade": "MEDIA",
                "categoria": "nicho",
                "titulo": f"{len(nichos_abertos)} nichos eleitorais sem concorrência",
                "descricao": f"Nichos abertos: {', '.join(n['nicho'] for n in nichos_abertos[:4])}. "
                             f"Posicionamento nesses segmentos pode capturar votos sem disputar com rivais.",
                "impacto_votos": len(nichos_abertos) * 600,
            })

        if ritmo_necessario_mes > 1000:
            recomendacoes.append({
                "prioridade": "URGENTE",
                "categoria": "crescimento",
                "titulo": f"Ritmo de {ritmo_necessario_mes:,} novos cadastros/mês necessário",
                "descricao": f"Com {meses_restantes} meses para a eleição, são necessários "
                             f"{cadastros_necessarios:,} cadastros adicionais para a meta segura. "
                             f"Hoje o ritmo estimado é insuficiente.",
                "impacto_votos": round(cadastros_necessarios * proj["taxa_conversao"] * 0.715 * proj["multiplicador_medio"]),
            })

        # Consolidar redutos
        if len(redutos_proprios) > 3:
            recomendacoes.append({
                "prioridade": "MEDIA",
                "categoria": "consolidacao",
                "titulo": f"Consolidar {len(redutos_proprios)} redutos próprios com baixa pressão rival",
                "descricao": f"Bairros {', '.join(redutos_proprios[:4])} são territórios com nossa presença "
                             f"e pouca resistência. Investir em fidelização e multiplicadores locais.",
                "impacto_votos": len(redutos_proprios) * 200,
            })

        recomendacoes.sort(key=lambda x: {"URGENTE": 0, "ALTA": 1, "MEDIA": 2}.get(x["prioridade"], 3))

        return {
            "foco": foco,
            "resumo": {
                "total_cadastros": total_cadastros,
                "votos_projetados": proj["total_votos_estimado"],
                "score_viabilidade": score["score_total"],
                "dias_para_eleicao": dias_restantes,
                "meses_restantes": meses_restantes,
                "cadastros_necessarios": cadastros_necessarios,
                "ritmo_necessario_mes": ritmo_necessario_mes,
            },
            "mapa_territorial": {
                "redutos_proprios": redutos_proprios,
                "campos_disputados": campos_disputados,
                "territorios_rivais": [b for b, d in pressao_por_bairro.items()
                                       if d["classificacao"] == "TERRITORIO_RIVAL"],
                "zonas_neutras": [b for b, d in pressao_por_bairro.items()
                                  if d["classificacao"] == "ZONA_NEUTRA"],
                "detalhe": pressao_por_bairro,
            },
            "oportunidades_territoriais": oportunidades[:8],
            "nichos": {
                "saturados": nichos_saturados,
                "abertos": nichos_abertos,
            },
            "recomendacoes": recomendacoes,
            "concorrentes_analisados": len(concs),
        }
