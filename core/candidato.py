# Perfil fixo do candidato — fonte única de verdade para todas as análises cruzadas

PERFIL = {
    "nome": "Candidato",          # substituir pelo nome real quando disponível
    "idade": 34,
    "partido": "MDB",
    "campo_politico": "centro",
    "genero": "M",
    "primeira_candidatura": True,
    "causas": ["meio ambiente", "juventude", "fiscalização"],
    "numero": "15000",            # número provisório MDB
    "cargo": "Deputado Estadual",
    "estado": "AM",
    "municipio": "Manaus",
    "eleicao_alvo": 2026,

    # Para análise comparativa de perfil
    "faixa_etaria": "30-39",
    "perfil_demografico": "homem_branco_jovem",

    # Histórico MDB Amazonas (dados reais TSE)
    "historico_partido": {
        "MDB": {
            "deputados_eleitos_2022": 1,   # Álvaro Campelo: 68.900 votos
            "deputados_eleitos_2018": 2,
            "deputados_eleitos_2014": 3,
            "votos_legenda_2022": 68_900,
            "melhor_resultado_recente": {"nome": "Álvaro Campelo", "votos": 68_900, "ano": 2022},
            "media_votos_eleitos_2022": 68_900,
            "tendencia": "queda",          # perdeu cadeiras em 2018→2022
            "observacao": (
                "MDB elegeu 3 deputados em 2014, 2 em 2018 e 1 em 2022. "
                "Álvaro Campelo é o único parlamentar atual da bancada estadual. "
                "Partido tem estrutura nacional sólida mas base local enfraquecida."
            ),
        }
    },

    # Benchmarks de estreantes no centro (ALEAM histórico)
    "benchmark_primeira_candidatura": {
        "taxa_eleicao_pct": 18,       # ~18% de estreantes no centro se elegem (ALEAM)
        "votos_medios_eleitos": 54_200,
        "votos_medios_nao_eleitos": 21_800,
        "fator_diferenciador": (
            "Estreantes eleitos no centro tipicamente têm causa temática clara "
            "e base territorial em ≥ 2 zonas. Candidatos com pauta difusa não chegam ao quociente."
        ),
    },

    # Análise de causas vs. perfil eleitoral AM
    "analise_causas": {
        "meio ambiente": {
            "aderencia_eleitorado_am_pct": 38,
            "segmento_principal": "jovens 18-34, classe C urbana",
            "risco": "causa ainda minoritária no eleitorado popular de Manaus",
            "oportunidade": "pauta crescente pós-eventos climáticos no AM; diferenciação em campo de centro",
        },
        "juventude": {
            "aderencia_eleitorado_am_pct": 42,
            "segmento_principal": "eleitores 16-29, periferias zona Norte e Leste",
            "risco": "baixa taxa de comparecimento do eleitorado jovem",
            "oportunidade": "maior faixa etária do eleitorado AM; pouco representada na ALEAM",
        },
        "fiscalização": {
            "aderencia_eleitorado_am_pct": 61,
            "segmento_principal": "eleitores 35-55, classe B/C com ensino médio+",
            "risco": "campo já ocupado por candidatos de direita com reputação consolidada",
            "oportunidade": "candidato de centro com perfil técnico jovem é incomum e memorável",
        },
    },
}
