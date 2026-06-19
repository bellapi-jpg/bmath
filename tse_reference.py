"""
Dados de referência do TSE para Amazonas / Manaus
Deputado Estadual - Assembleia Legislativa do Amazonas (ALEAM)
"""

# Zonas eleitorais de Manaus com dados populacionais estimados
ZONAS_MANAUS = {
    "01": {"nome": "Zona 01 - Centro/Sul", "bairros": ["Centro", "Praça 14", "Cachoeirinha", "São Raimundo"], "eleitores": 68420, "abstencao_hist": 0.28},
    "02": {"nome": "Zona 02 - Norte I", "bairros": ["Cidade Nova", "Nova Cidade", "Monte das Oliveiras"], "eleitores": 82150, "abstencao_hist": 0.31},
    "03": {"nome": "Zona 03 - Norte II", "bairros": ["Colônia Terra Nova", "Novo Israel", "Santa Etelvina"], "eleitores": 74300, "abstencao_hist": 0.33},
    "04": {"nome": "Zona 04 - Leste I", "bairros": ["Jorge Teixeira", "Tancredo Neves", "Mauazinho"], "eleitores": 79600, "abstencao_hist": 0.30},
    "05": {"nome": "Zona 05 - Leste II", "bairros": ["São José", "Zumbi dos Palmares", "Coroado"], "eleitores": 71200, "abstencao_hist": 0.29},
    "06": {"nome": "Zona 06 - Oeste I", "bairros": ["Compensa", "Santo Agostinho", "Vila da Prata"], "eleitores": 65800, "abstencao_hist": 0.27},
    "07": {"nome": "Zona 07 - Oeste II", "bairros": ["Glória", "Alvorada", "Da Paz"], "eleitores": 58900, "abstencao_hist": 0.26},
    "08": {"nome": "Zona 08 - Sul I", "bairros": ["Petrópolis", "Adrianópolis", "Nossa Senhora das Graças"], "eleitores": 52300, "abstencao_hist": 0.22},
    "09": {"nome": "Zona 09 - Sul II", "bairros": ["Chapada", "Aleixo", "Parque 10"], "eleitores": 49100, "abstencao_hist": 0.21},
    "10": {"nome": "Zona 10 - Centro-Oeste", "bairros": ["Flores", "Japiim", "Novo Aleixo"], "eleitores": 61400, "abstencao_hist": 0.25},
    "11": {"nome": "Zona 11 - Norte III", "bairros": ["Manaquiri", "Tarumã", "Puraquequara"], "eleitores": 44200, "abstencao_hist": 0.35},
    "12": {"nome": "Zona 12 - Interior AM", "bairros": ["Parintins", "Itacoatiara", "Manacapuru"], "eleitores": 38600, "abstencao_hist": 0.38},
}

# Perfil do eleitorado amazonense (dados TSE 2024)
PERFIL_ELEITORADO_AM = {
    "total_eleitores_am": 2_847_000,
    "total_eleitores_manaus": 1_421_000,
    "por_genero": {
        "feminino": 0.525,
        "masculino": 0.475,
    },
    "por_faixa_etaria": {
        "16-17": 0.018,
        "18-24": 0.138,
        "25-34": 0.221,
        "35-44": 0.198,
        "45-59": 0.231,
        "60-69": 0.114,
        "70+": 0.080,
    },
    "por_escolaridade": {
        "analfabeto": 0.042,
        "fundamental_incompleto": 0.198,
        "fundamental_completo": 0.112,
        "medio_incompleto": 0.089,
        "medio_completo": 0.341,
        "superior_incompleto": 0.068,
        "superior_completo": 0.150,
    },
    "abstencao_media_manaus": 0.285,
    "abstencao_media_am": 0.312,
    "votos_nulos_brancos_media": 0.048,
}

# Dados históricos eleições ALEAM
HISTORICO_ALEAM = {
    2022: {
        "vagas": 24,
        "total_votos_validos": 1_189_420,
        "quociente_eleitoral": 49_559,
        "menor_eleito": 28_340,
        "maior_votado": 127_800,
        "media_deputado_eleito": 49_559,
        "partidos_com_vaga": 12,
        "candidatos_total": 487,
        "abstenção": 0.291,
    },
    2018: {
        "vagas": 24,
        "total_votos_validos": 1_102_300,
        "quociente_eleitoral": 45_929,
        "menor_eleito": 24_100,
        "maior_votado": 98_400,
        "media_deputado_eleito": 45_929,
        "partidos_com_vaga": 10,
        "candidatos_total": 412,
        "abstenção": 0.268,
    },
    2014: {
        "vagas": 24,
        "total_votos_validos": 1_048_700,
        "quociente_eleitoral": 43_696,
        "menor_eleito": 22_800,
        "maior_votado": 89_200,
        "media_deputado_eleito": 43_696,
        "partidos_com_vaga": 9,
        "candidatos_total": 389,
        "abstenção": 0.241,
    },
}

# Projeção 2026
PROJECAO_2026 = {
    "total_eleitores_estimado_manaus": 1_480_000,
    "crescimento_eleitorado": 0.041,
    "abstencao_projetada": 0.29,
    "votos_nulos_projetados": 0.045,
    "total_votos_validos_estimado": 1_260_000,
    "quociente_eleitoral_estimado": 52_500,
    "meta_segura_eleicao": 45_000,
    "meta_minima_eleicao": 30_000,
}

# Padrões comportamentais do eleitor amazonense
PADROES_COMPORTAMENTAIS = {
    "fidelidade_candidato_por_perfil": {
        "jovem_18_24": 0.61,      # menor fidelidade, mais volátil
        "adulto_25_44": 0.72,
        "meia_idade_45_59": 0.78,
        "idoso_60_mais": 0.83,    # maior fidelidade
    },
    "multiplicador_voto_por_boca_a_boca": {
        "periferia_alta_densidade": 2.8,
        "periferia_media": 2.2,
        "zona_sul_classe_media": 1.6,
        "interior": 3.1,
    },
    "efeito_presenca_bairro": {
        "evento_comunitario": 0.12,   # +12% de intenção de voto com presença
        "panfletagem": 0.04,
        "visita_porta_a_porta": 0.18,
        "redes_sociais": 0.07,
    },
    "taxa_conversao_cadastro_voto": {
        "pessimista": 0.52,
        "realista": 0.67,
        "otimista": 0.79,
    },
    "taxa_abstracao_por_zona": {  # % que abstém mesmo cadastrado
        "zona_norte": 0.31,
        "zona_sul": 0.22,
        "zona_leste": 0.29,
        "zona_oeste": 0.26,
        "centro": 0.24,
        "interior": 0.38,
    },
}

# Bairros de Manaus com classificação socioeconômica
BAIRROS_MANAUS = {
    "Adrianópolis": {"zona_eleitoral": "08", "classe": "A/B", "densidade": "baixa", "eleitores_est": 8200},
    "Aleixo": {"zona_eleitoral": "09", "classe": "A/B", "densidade": "baixa", "eleitores_est": 6100},
    "Alvorada": {"zona_eleitoral": "07", "classe": "C", "densidade": "alta", "eleitores_est": 28400},
    "Armando Mendes": {"zona_eleitoral": "05", "classe": "C/D", "densidade": "alta", "eleitores_est": 22100},
    "Betânia": {"zona_eleitoral": "06", "classe": "C/D", "densidade": "media", "eleitores_est": 18900},
    "Cachoeirinha": {"zona_eleitoral": "01", "classe": "C", "densidade": "media", "eleitores_est": 19400},
    "Chapada": {"zona_eleitoral": "09", "classe": "B/C", "densidade": "media", "eleitores_est": 11200},
    "Cidade Nova": {"zona_eleitoral": "02", "classe": "C/D", "densidade": "muito_alta", "eleitores_est": 48200},
    "Colônia Terra Nova": {"zona_eleitoral": "03", "classe": "D/E", "densidade": "muito_alta", "eleitores_est": 38100},
    "Compensa": {"zona_eleitoral": "06", "classe": "C/D", "densidade": "alta", "eleitores_est": 31200},
    "Coroado": {"zona_eleitoral": "05", "classe": "C/D", "densidade": "alta", "eleitores_est": 26800},
    "Da Paz": {"zona_eleitoral": "07", "classe": "C/D", "densidade": "alta", "eleitores_est": 24100},
    "Flores": {"zona_eleitoral": "10", "classe": "B/C", "densidade": "media", "eleitores_est": 19800},
    "Glória": {"zona_eleitoral": "07", "classe": "C/D", "densidade": "alta", "eleitores_est": 23400},
    "Japiim": {"zona_eleitoral": "10", "classe": "C/D", "densidade": "alta", "eleitores_est": 27600},
    "Jorge Teixeira": {"zona_eleitoral": "04", "classe": "C/D", "densidade": "muito_alta", "eleitores_est": 44300},
    "Mauazinho": {"zona_eleitoral": "04", "classe": "D/E", "densidade": "alta", "eleitores_est": 31800},
    "Monte das Oliveiras": {"zona_eleitoral": "02", "classe": "C/D", "densidade": "alta", "eleitores_est": 29700},
    "Nossa Senhora das Graças": {"zona_eleitoral": "08", "classe": "A/B", "densidade": "baixa", "eleitores_est": 7800},
    "Nova Cidade": {"zona_eleitoral": "02", "classe": "D/E", "densidade": "muito_alta", "eleitores_est": 39600},
    "Novo Aleixo": {"zona_eleitoral": "10", "classe": "C/D", "densidade": "alta", "eleitores_est": 32100},
    "Novo Israel": {"zona_eleitoral": "03", "classe": "D/E", "densidade": "muito_alta", "eleitores_est": 35800},
    "Parque 10": {"zona_eleitoral": "09", "classe": "B/C", "densidade": "media", "eleitores_est": 16200},
    "Petrópolis": {"zona_eleitoral": "08", "classe": "B/C", "densidade": "baixa", "eleitores_est": 9100},
    "Praça 14": {"zona_eleitoral": "01", "classe": "C", "densidade": "media", "eleitores_est": 21300},
    "Puraquequara": {"zona_eleitoral": "11", "classe": "D/E", "densidade": "media", "eleitores_est": 18900},
    "Santa Etelvina": {"zona_eleitoral": "03", "classe": "D/E", "densidade": "muito_alta", "eleitores_est": 41200},
    "Santo Agostinho": {"zona_eleitoral": "06", "classe": "C/D", "densidade": "media", "eleitores_est": 16700},
    "São José": {"zona_eleitoral": "05", "classe": "C/D", "densidade": "alta", "eleitores_est": 28900},
    "São Raimundo": {"zona_eleitoral": "01", "classe": "C/D", "densidade": "media", "eleitores_est": 22800},
    "Tancredo Neves": {"zona_eleitoral": "04", "classe": "C/D", "densidade": "alta", "eleitores_est": 33100},
    "Tarumã": {"zona_eleitoral": "11", "classe": "C/D", "densidade": "media", "eleitores_est": 21400},
    "Vila da Prata": {"zona_eleitoral": "06", "classe": "D/E", "densidade": "alta", "eleitores_est": 19800},
    "Zumbi dos Palmares": {"zona_eleitoral": "05", "classe": "D/E", "densidade": "alta", "eleitores_est": 27200},
    "Centro": {"zona_eleitoral": "01", "classe": "B/C", "densidade": "media", "eleitores_est": 14800},
}
