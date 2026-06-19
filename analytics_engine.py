"""
Motor de análise matemática e projeções eleitorais
Deputado Estadual - Amazonas 2026
"""
import numpy as np
import pandas as pd
from scipy import stats
from typing import Dict, List, Tuple, Optional
import json
from tse_reference import (
    ZONAS_MANAUS, PERFIL_ELEITORADO_AM, HISTORICO_ALEAM,
    PROJECAO_2026, PADROES_COMPORTAMENTAIS, BAIRROS_MANAUS
)


class ElectoralAnalytics:

    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()
        self._normalize_columns()

    def _normalize_columns(self):
        col_map = {}
        for col in self.df.columns:
            c = col.strip().lower()
            if any(x in c for x in ["nome", "name"]):
                col_map[col] = "nome"
            elif any(x in c for x in ["bairro", "neighborhood"]):
                col_map[col] = "bairro"
            elif any(x in c for x in ["zona", "zone"]):
                col_map[col] = "zona"
            elif any(x in c for x in ["genero", "gênero", "sexo", "gender"]):
                col_map[col] = "genero"
            elif any(x in c for x in ["idade", "age", "nasc"]):
                col_map[col] = "idade"
            elif any(x in c for x in ["telefone", "phone", "cel", "contato"]):
                col_map[col] = "telefone"
            elif any(x in c for x in ["escolaridade", "escola", "educ"]):
                col_map[col] = "escolaridade"
        self.df.rename(columns=col_map, inplace=True)

    # ── Estatísticas descritivas do cadastro ──────────────────────────────

    def resumo_cadastro(self) -> Dict:
        total = len(self.df)
        por_bairro = {}
        por_zona = {}
        por_genero = {}
        por_faixa = {}

        if "bairro" in self.df.columns:
            por_bairro = self.df["bairro"].value_counts().head(20).to_dict()

        if "zona" in self.df.columns:
            por_zona = self.df["zona"].value_counts().to_dict()

        if "genero" in self.df.columns:
            raw = self.df["genero"].str.upper().str.strip()
            masc = int(raw.isin(["M", "MASCULINO", "MALE"]).sum())
            fem = int(raw.isin(["F", "FEMININO", "FEMALE"]).sum())
            por_genero = {"Masculino": masc, "Feminino": fem, "Não informado": total - masc - fem}

        if "idade" in self.df.columns:
            idades = pd.to_numeric(self.df["idade"], errors="coerce").dropna()
            bins = [0, 17, 24, 34, 44, 59, 69, 120]
            labels = ["≤17", "18-24", "25-34", "35-44", "45-59", "60-69", "70+"]
            faixas = pd.cut(idades, bins=bins, labels=labels)
            por_faixa = faixas.value_counts().to_dict()
            por_faixa = {str(k): int(v) for k, v in por_faixa.items()}

        return {
            "total_cadastros": total,
            "por_bairro": {str(k): int(v) for k, v in por_bairro.items()},
            "por_zona": {str(k): int(v) for k, v in por_zona.items()},
            "por_genero": por_genero,
            "por_faixa_etaria": por_faixa,
            "bairros_distintos": int(self.df["bairro"].nunique()) if "bairro" in self.df.columns else 0,
            "zonas_distintas": int(self.df["zona"].nunique()) if "zona" in self.df.columns else 0,
        }

    # ── Análise de cobertura territorial ─────────────────────────────────

    def analise_territorial(self) -> Dict:
        resultado = {}
        bairros_ref = BAIRROS_MANAUS

        if "bairro" not in self.df.columns:
            return {"erro": "Coluna bairro não encontrada"}

        contagem = self.df["bairro"].value_counts().to_dict()

        for bairro, qtd in contagem.items():
            info = bairros_ref.get(bairro, {})
            eleitores_est = info.get("eleitores_est", 15000)
            penetracao = min((qtd / eleitores_est) * 100, 100)
            classe = info.get("classe", "N/D")
            densidade = info.get("densidade", "N/D")
            zona = info.get("zona_eleitoral", "N/D")

            # ROI: bairros com alta densidade e baixa penetração têm maior potencial
            densidade_score = {"muito_alta": 1.0, "alta": 0.8, "media": 0.6, "baixa": 0.4}.get(densidade, 0.5)
            roi = round((1 - penetracao / 100) * densidade_score * eleitores_est / 1000, 2)

            resultado[bairro] = {
                "cadastros": int(qtd),
                "eleitores_estimados": eleitores_est,
                "penetracao_pct": round(penetracao, 2),
                "classe_social": classe,
                "densidade": densidade,
                "zona_eleitoral": zona,
                "roi_potencial": roi,
            }

        # Bairros sem presença (potencial inexplorado)
        sem_presenca = [b for b in bairros_ref if b not in contagem]

        return {
            "por_bairro": resultado,
            "bairros_sem_presenca": sem_presenca,
            "cobertura_total_pct": round(len(contagem) / len(bairros_ref) * 100, 1),
        }

    # ── Modelo de projeção de votos ───────────────────────────────────────

    def projecao_votos(self, cenario: str = "realista") -> Dict:
        total_cadastros = len(self.df)
        ref = PROJECAO_2026
        padroes = PADROES_COMPORTAMENTAIS

        taxa_conv = padroes["taxa_conversao_cadastro_voto"][cenario]

        # Calcular multiplicador médio ponderado por bairro
        mult_medio = 2.2
        if "bairro" in self.df.columns:
            mults = []
            for bairro in self.df["bairro"].unique():
                info = BAIRROS_MANAUS.get(bairro, {})
                dens = info.get("densidade", "media")
                m = padroes["multiplicador_voto_por_boca_a_boca"].get(
                    "periferia_alta_densidade" if dens in ["alta", "muito_alta"]
                    else "periferia_media" if dens == "media"
                    else "zona_sul_classe_media", 2.0
                )
                mults.append(m)
            mult_medio = float(np.mean(mults)) if mults else 2.2

        # Votos diretos (cadastros que efetivamente votam)
        votos_diretos = total_cadastros * taxa_conv * (1 - ref["abstencao_projetada"])

        # Votos indiretos (efeito multiplicador: cada apoiador influencia outros)
        votos_indiretos = votos_diretos * (mult_medio - 1) * 0.35  # 35% de eficiência de conversão

        total_votos = votos_diretos + votos_indiretos

        quociente = ref["quociente_eleitoral_estimado"]
        meta_segura = ref["meta_segura_eleicao"]
        meta_minima = ref["meta_minima_eleicao"]

        deficit_quociente = max(0, quociente - total_votos)
        prob_eleicao = self._calcular_probabilidade(total_votos, quociente)

        return {
            "cenario": cenario,
            "total_cadastros": total_cadastros,
            "taxa_conversao": taxa_conv,
            "votos_diretos_estimados": round(votos_diretos),
            "votos_indiretos_estimados": round(votos_indiretos),
            "total_votos_estimado": round(total_votos),
            "quociente_eleitoral_2026": quociente,
            "meta_segura": meta_segura,
            "meta_minima": meta_minima,
            "deficit_para_quociente": round(deficit_quociente),
            "pct_quociente_atingido": round((total_votos / quociente) * 100, 1),
            "probabilidade_eleicao_pct": round(prob_eleicao * 100, 1),
            "multiplicador_medio": round(mult_medio, 2),
        }

    def _calcular_probabilidade(self, votos_estimados: float, quociente: float) -> float:
        ratio = votos_estimados / quociente
        # Função sigmoide ajustada para realidade eleitoral brasileira
        # 50% de chance quando está em 70% do quociente (incerteza real)
        prob = 1 / (1 + np.exp(-6 * (ratio - 0.75)))
        return min(max(prob, 0.01), 0.99)

    # ── Simulação Monte Carlo ─────────────────────────────────────────────

    def monte_carlo(self, n_simulacoes: int = 10000) -> Dict:
        total_cadastros = len(self.df)
        ref = PROJECAO_2026
        padroes = PADROES_COMPORTAMENTAIS

        rng = np.random.default_rng(42)

        # Parâmetros com distribuições
        taxa_conv = rng.beta(a=7, b=3.5, size=n_simulacoes)  # média ~0.67
        taxa_conv = np.clip(taxa_conv, 0.45, 0.90)

        abstencao = rng.beta(a=5, b=13, size=n_simulacoes)    # média ~0.28
        abstencao = np.clip(abstencao, 0.15, 0.45)

        multiplicador = rng.normal(loc=2.2, scale=0.4, size=n_simulacoes)
        multiplicador = np.clip(multiplicador, 1.2, 4.0)

        eficiencia_mult = rng.beta(a=3, b=5, size=n_simulacoes)  # média ~0.37
        eficiencia_mult = np.clip(eficiencia_mult, 0.15, 0.60)

        votos_diretos = total_cadastros * taxa_conv * (1 - abstencao)
        votos_indiretos = votos_diretos * (multiplicador - 1) * eficiencia_mult
        votos_totais = votos_diretos + votos_indiretos

        quociente = ref["quociente_eleitoral_estimado"]
        meta_minima = ref["meta_minima_eleicao"]

        eleito = votos_totais >= quociente
        acima_minimo = votos_totais >= meta_minima

        percentis = np.percentile(votos_totais, [5, 10, 25, 50, 75, 90, 95])

        hist_vals, hist_bins = np.histogram(votos_totais, bins=50)
        histograma = [
            {"bin_inicio": round(float(hist_bins[i])), "bin_fim": round(float(hist_bins[i+1])), "freq": int(hist_vals[i])}
            for i in range(len(hist_vals))
        ]

        return {
            "n_simulacoes": n_simulacoes,
            "media_votos": round(float(np.mean(votos_totais))),
            "mediana_votos": round(float(np.median(votos_totais))),
            "desvio_padrao": round(float(np.std(votos_totais))),
            "prob_eleicao_pct": round(float(np.mean(eleito)) * 100, 1),
            "prob_acima_minimo_pct": round(float(np.mean(acima_minimo)) * 100, 1),
            "intervalo_confianca_90": {
                "min": round(float(percentis[1])),
                "max": round(float(percentis[8] if len(percentis) > 8 else percentis[-1])),
            },
            "percentis": {
                "p5": round(float(percentis[0])),
                "p10": round(float(percentis[1])),
                "p25": round(float(percentis[2])),
                "p50": round(float(percentis[3])),
                "p75": round(float(percentis[4])),
                "p90": round(float(percentis[5])),
                "p95": round(float(percentis[6])),
            },
            "histograma": histograma,
            "quociente_referencia": quociente,
        }

    # ── Análise de gaps e metas por zona ─────────────────────────────────

    def analise_gaps_zonas(self) -> Dict:
        if "zona" not in self.df.columns and "bairro" not in self.df.columns:
            return {}

        resultado = {}
        ref_zonas = ZONAS_MANAUS

        # Mapear cadastros para zonas via bairro
        if "bairro" in self.df.columns:
            df_temp = self.df.copy()
            df_temp["zona_mapeada"] = df_temp["bairro"].map(
                lambda b: BAIRROS_MANAUS.get(b, {}).get("zona_eleitoral", "N/D")
            )
            por_zona = df_temp["zona_mapeada"].value_counts().to_dict()
        else:
            por_zona = self.df["zona"].value_counts().to_dict()

        meta_total = PROJECAO_2026["quociente_eleitoral_estimado"]

        for zona_id, info in ref_zonas.items():
            cadastros = int(por_zona.get(zona_id, 0))
            eleitores = info["eleitores"]
            abstencao = info["abstencao_hist"]
            votantes_est = eleitores * (1 - abstencao)

            penetracao = (cadastros / eleitores * 100) if eleitores > 0 else 0
            votos_est_zona = cadastros * 0.67 * (1 - abstencao) * 2.2 * 1.35

            participacao_meta = (votos_est_zona / meta_total * 100) if meta_total > 0 else 0
            potencial_residual = max(0, votantes_est - votos_est_zona)

            resultado[zona_id] = {
                "nome": info["nome"],
                "bairros": info["bairros"],
                "eleitores_totais": eleitores,
                "cadastros": cadastros,
                "penetracao_pct": round(penetracao, 2),
                "votantes_estimados_zona": round(votantes_est),
                "votos_estimados_candidato": round(votos_est_zona),
                "contribuicao_meta_pct": round(participacao_meta, 1),
                "potencial_residual": round(potencial_residual),
                "abstencao_historica": abstencao,
                "prioridade": "ALTA" if penetracao < 1 and eleitores > 50000 else
                              "MEDIA" if penetracao < 3 else "BAIXA",
            }

        return resultado

    # ── Projeção de crescimento ───────────────────────────────────────────

    def projecao_crescimento(self, cadastros_por_mes: List[int] = None) -> Dict:
        if cadastros_por_mes is None:
            total = len(self.df)
            cadastros_por_mes = [
                max(1, round(total * 0.04)),
                max(1, round(total * 0.05)),
                max(1, round(total * 0.06)),
                max(1, round(total * 0.07)),
                max(1, round(total * 0.08)),
                max(1, round(total * 0.10)),
                max(1, round(total * 0.12)),
                max(1, round(total * 0.15)),
                max(1, round(total * 0.18)),
                max(1, round(total * 0.15)),
            ]

        acumulado = list(np.cumsum(cadastros_por_mes))
        meses = ["Set/25", "Out/25", "Nov/25", "Dez/25", "Jan/26", "Fev/26",
                 "Mar/26", "Abr/26", "Mai/26", "Jun/26"]

        projecoes = []
        for i, (mes, acc) in enumerate(zip(meses, acumulado)):
            votos_est = acc * 0.67 * (1 - 0.285) * 2.2 * 1.35
            projecoes.append({
                "mes": mes,
                "cadastros_novos": cadastros_por_mes[i] if i < len(cadastros_por_mes) else 0,
                "cadastros_acumulados": round(acc),
                "votos_estimados": round(votos_est),
                "pct_meta": round((votos_est / PROJECAO_2026["quociente_eleitoral_estimado"]) * 100, 1),
            })

        return {"projecao_mensal": projecoes}

    # ── Score de viabilidade ──────────────────────────────────────────────

    def score_viabilidade(self) -> Dict:
        resumo = self.resumo_cadastro()
        proj_real = self.projecao_votos("realista")
        mc = self.monte_carlo(5000)

        total = resumo["total_cadastros"]
        bairros = resumo["bairros_distintos"]
        zonas = resumo["zonas_distintas"]
        prob_mc = mc["prob_eleicao_pct"]
        pct_quoc = proj_real["pct_quociente_atingido"]

        score_volume = min(total / 15000 * 30, 30)
        score_dispersao = min((bairros / 20) * 20 + (zonas / 10) * 10, 30)
        score_probabilidade = prob_mc * 0.4

        score_total = score_volume + score_dispersao + score_probabilidade
        score_total = min(round(score_total, 1), 100)

        if score_total >= 70:
            classificacao = "FORTE"
            cor = "#22c55e"
        elif score_total >= 45:
            classificacao = "COMPETITIVO"
            cor = "#f59e0b"
        elif score_total >= 25:
            classificacao = "EM CONSTRUÇÃO"
            cor = "#f97316"
        else:
            classificacao = "CRÍTICO"
            cor = "#ef4444"

        return {
            "score_total": score_total,
            "classificacao": classificacao,
            "cor": cor,
            "componentes": {
                "volume_cadastral": round(score_volume, 1),
                "dispersao_territorial": round(score_dispersao, 1),
                "probabilidade_matematica": round(score_probabilidade, 1),
            },
            "pct_quociente_atingido": pct_quoc,
            "prob_eleicao_mc": prob_mc,
        }

    # ── Recomendações estratégicas ────────────────────────────────────────

    def recomendacoes_estrategicas(self) -> List[Dict]:
        territorial = self.analise_territorial()
        resumo = self.resumo_cadastro()
        proj = self.projecao_votos("realista")

        recomendacoes = []

        # Bairros de alta prioridade sem presença
        sem_presenca = territorial.get("bairros_sem_presenca", [])
        alta_densidade_sem_presenca = [
            b for b in sem_presenca
            if BAIRROS_MANAUS.get(b, {}).get("densidade") in ["alta", "muito_alta"]
        ]
        if alta_densidade_sem_presenca:
            recomendacoes.append({
                "prioridade": "URGENTE",
                "tipo": "territorial",
                "titulo": "Bairros de alta densidade sem presença",
                "descricao": f"{len(alta_densidade_sem_presenca)} bairros densamente populosos sem nenhum cadastro. Potencial de milhares de votos inexplorados.",
                "bairros": alta_densidade_sem_presenca[:5],
                "impacto_estimado": len(alta_densidade_sem_presenca) * 800,
            })

        # Meta de cadastros
        deficit = proj["deficit_para_quociente"]
        cadastros_necessarios = round(deficit / (0.67 * 0.715 * 2.2 * 1.35))
        if cadastros_necessarios > 0:
            recomendacoes.append({
                "prioridade": "ALTA",
                "tipo": "volume",
                "titulo": "Meta de novos cadastros",
                "descricao": f"Para atingir o quociente eleitoral, são necessários aproximadamente {cadastros_necessarios:,} novos cadastros.",
                "impacto_estimado": deficit,
            })

        # Gênero
        genero = resumo.get("por_genero", {})
        total_gen = sum(genero.values())
        if total_gen > 0:
            pct_fem = genero.get("Feminino", 0) / total_gen
            pct_masc = genero.get("Masculino", 0) / total_gen
            if abs(pct_fem - 0.525) > 0.10:
                sub = "feminino" if pct_fem < 0.525 else "masculino"
                recomendacoes.append({
                    "prioridade": "MEDIA",
                    "tipo": "demografico",
                    "titulo": f"Sub-representação do eleitorado {sub}",
                    "descricao": f"Sua base tem {pct_fem*100:.0f}% feminino vs {52.5:.0f}% do eleitorado AM. Ampliar alcance neste segmento.",
                    "impacto_estimado": round(total_gen * 0.08 * 0.67),
                })

        recomendacoes.append({
            "prioridade": "MEDIA",
            "tipo": "estrategia",
            "titulo": "Priorizar Zona Norte e Leste",
            "descricao": "Zonas com maior volume eleitoral e taxas de abstenção razoáveis. Maior ROI por evento de campanha.",
            "impacto_estimado": 3200,
        })

        return recomendacoes
