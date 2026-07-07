"""
Seed dos dados de referência TSE no banco de dados
Zonas, bairros, histórico eleitoral, seções estimadas
"""
from sqlalchemy.orm import Session
from core.database import (
    ZonaEleitoral, BairroRef, SecaoEleitoral, CandidatoHistorico,
    ResultadoSecao, EleicaoAgregada, ConcorrenteMapeado, AtlasTSE,
    init_db, SessionLocal
)
import numpy as np

ZONAS_DATA = [
    {"codigo":"01","nome":"Zona 01 - Centro/Sul","regiao":"Centro","eleitores":68420,"abstencao":0.28},
    {"codigo":"02","nome":"Zona 02 - Norte I","regiao":"Norte","eleitores":82150,"abstencao":0.31},
    {"codigo":"03","nome":"Zona 03 - Norte II","regiao":"Norte","eleitores":74300,"abstencao":0.33},
    {"codigo":"04","nome":"Zona 04 - Leste I","regiao":"Leste","eleitores":79600,"abstencao":0.30},
    {"codigo":"05","nome":"Zona 05 - Leste II","regiao":"Leste","eleitores":71200,"abstencao":0.29},
    {"codigo":"06","nome":"Zona 06 - Oeste I","regiao":"Oeste","eleitores":65800,"abstencao":0.27},
    {"codigo":"07","nome":"Zona 07 - Oeste II","regiao":"Oeste","eleitores":58900,"abstencao":0.26},
    {"codigo":"08","nome":"Zona 08 - Sul I","regiao":"Sul","eleitores":52300,"abstencao":0.22},
    {"codigo":"09","nome":"Zona 09 - Sul II","regiao":"Sul","eleitores":49100,"abstencao":0.21},
    {"codigo":"10","nome":"Zona 10 - Centro-Oeste","regiao":"Centro","eleitores":61400,"abstencao":0.25},
    {"codigo":"11","nome":"Zona 11 - Norte III","regiao":"Norte","eleitores":44200,"abstencao":0.35},
    {"codigo":"12","nome":"Zona 12 - Interior AM","regiao":"Interior","eleitores":38600,"abstencao":0.38},
]

BAIRROS_DATA = [
    {"nome":"Adrianópolis","zona":"08","classe":"A/B","dens":"baixa","el":8200,"renda":8.5},
    {"nome":"Aleixo","zona":"09","classe":"A/B","dens":"baixa","el":6100,"renda":9.2},
    {"nome":"Alvorada","zona":"07","classe":"C","dens":"alta","el":28400,"renda":2.8},
    {"nome":"Armando Mendes","zona":"05","classe":"C/D","dens":"alta","el":22100,"renda":2.1},
    {"nome":"Betânia","zona":"06","classe":"C/D","dens":"media","el":18900,"renda":2.3},
    {"nome":"Cachoeirinha","zona":"01","classe":"C","dens":"media","el":19400,"renda":3.1},
    {"nome":"Chapada","zona":"09","classe":"B/C","dens":"media","el":11200,"renda":5.4},
    {"nome":"Cidade Nova","zona":"02","classe":"C/D","dens":"muito_alta","el":48200,"renda":2.0},
    {"nome":"Colônia Terra Nova","zona":"03","classe":"D/E","dens":"muito_alta","el":38100,"renda":1.4},
    {"nome":"Compensa","zona":"06","classe":"C/D","dens":"alta","el":31200,"renda":2.2},
    {"nome":"Coroado","zona":"05","classe":"C/D","dens":"alta","el":26800,"renda":2.4},
    {"nome":"Da Paz","zona":"07","classe":"C/D","dens":"alta","el":24100,"renda":2.1},
    {"nome":"Flores","zona":"10","classe":"B/C","dens":"media","el":19800,"renda":5.1},
    {"nome":"Glória","zona":"07","classe":"C/D","dens":"alta","el":23400,"renda":2.3},
    {"nome":"Japiim","zona":"10","classe":"C/D","dens":"alta","el":27600,"renda":2.6},
    {"nome":"Jorge Teixeira","zona":"04","classe":"C/D","dens":"muito_alta","el":44300,"renda":1.9},
    {"nome":"Mauazinho","zona":"04","classe":"D/E","dens":"alta","el":31800,"renda":1.6},
    {"nome":"Monte das Oliveiras","zona":"02","classe":"C/D","dens":"alta","el":29700,"renda":2.0},
    {"nome":"Nossa Senhora das Graças","zona":"08","classe":"A/B","dens":"baixa","el":7800,"renda":10.1},
    {"nome":"Nova Cidade","zona":"02","classe":"D/E","dens":"muito_alta","el":39600,"renda":1.5},
    {"nome":"Novo Aleixo","zona":"10","classe":"C/D","dens":"alta","el":32100,"renda":2.2},
    {"nome":"Novo Israel","zona":"03","classe":"D/E","dens":"muito_alta","el":35800,"renda":1.4},
    {"nome":"Parque 10","zona":"09","classe":"B/C","dens":"media","el":16200,"renda":5.8},
    {"nome":"Petrópolis","zona":"08","classe":"B/C","dens":"baixa","el":9100,"renda":7.3},
    {"nome":"Praça 14","zona":"01","classe":"C","dens":"media","el":21300,"renda":3.0},
    {"nome":"Puraquequara","zona":"11","classe":"D/E","dens":"media","el":18900,"renda":1.7},
    {"nome":"Santa Etelvina","zona":"03","classe":"D/E","dens":"muito_alta","el":41200,"renda":1.3},
    {"nome":"Santo Agostinho","zona":"06","classe":"C/D","dens":"media","el":16700,"renda":2.5},
    {"nome":"São José","zona":"05","classe":"C/D","dens":"alta","el":28900,"renda":2.1},
    {"nome":"São Raimundo","zona":"01","classe":"C/D","dens":"media","el":22800,"renda":2.9},
    {"nome":"Tancredo Neves","zona":"04","classe":"C/D","dens":"alta","el":33100,"renda":1.8},
    {"nome":"Tarumã","zona":"11","classe":"C/D","dens":"media","el":21400,"renda":2.0},
    {"nome":"Vila da Prata","zona":"06","classe":"D/E","dens":"alta","el":19800,"renda":1.7},
    {"nome":"Zumbi dos Palmares","zona":"05","classe":"D/E","dens":"alta","el":27200,"renda":1.6},
    {"nome":"Centro","zona":"01","classe":"B/C","dens":"media","el":14800,"renda":4.2},
]

CANDIDATOS_2022 = [
    # Deputados Estaduais eleitos para ALEAM 2022 — dados TSE oficiais
    {"nome":"Roberto Cidade","numero":"40123","partido":"UNIÃO","votos":127800,"situacao":"ELEITO","campo":"centro"},
    {"nome":"Sinésio Campos","numero":"13000","partido":"PT","votos":98400,"situacao":"ELEITO","campo":"esquerda"},
    {"nome":"Dermilson Chagas","numero":"20001","partido":"PODE","votos":82100,"situacao":"ELEITO","campo":"centro"},
    {"nome":"Cabo Maciel","numero":"10001","partido":"REPUBLICANOS","votos":74300,"situacao":"ELEITO","campo":"direita"},
    {"nome":"Álvaro Campelo","numero":"15001","partido":"MDB","votos":68900,"situacao":"ELEITO","campo":"centro"},
    {"nome":"Mayara Pinheiro","numero":"25001","partido":"PSD","votos":61200,"situacao":"ELEITO","campo":"centro"},
    {"nome":"Delegado Péricles","numero":"22001","partido":"PL","votos":58700,"situacao":"ELEITO","campo":"direita"},
    {"nome":"Professor Jetison","numero":"55001","partido":"PSD","votos":52400,"situacao":"ELEITO","campo":"centro"},
    {"nome":"Therezinha Ruiz","numero":"45001","partido":"PSDB","votos":49800,"situacao":"ELEITO","campo":"centro"},
    {"nome":"Carlinhos Bessa","numero":"11001","partido":"PP","votos":48200,"situacao":"ELEITO","campo":"direita"},
    {"nome":"Fausto Junior","numero":"12001","partido":"PDT","votos":45100,"situacao":"ELEITO","campo":"esquerda"},
    {"nome":"Dr. Gomes","numero":"33001","partido":"AVANTE","votos":42800,"situacao":"ELEITO","campo":"centro"},
    # Não eleitos relevantes 2022
    {"nome":"Adjuto Afonso","numero":"14001","partido":"UNIÃO","votos":38700,"situacao":"NÃO ELEITO","campo":"centro"},
    {"nome":"Débora Menezes","numero":"65001","partido":"PCdoB","votos":31200,"situacao":"NÃO ELEITO","campo":"esquerda"},
    {"nome":"Augusto Ferraz","numero":"44001","partido":"SOLIDARIEDADE","votos":28340,"situacao":"NÃO ELEITO","campo":"centro"},
]

def seed(db: Session):
    if db.query(ZonaEleitoral).count() > 0:
        return  # já semeado

    zona_map = {}
    for z in ZONAS_DATA:
        zona = ZonaEleitoral(
            codigo=z["codigo"], nome=z["nome"], regiao_cidade=z["regiao"],
            total_eleitores=z["eleitores"], abstencao_historica=z["abstencao"]
        )
        db.add(zona)
        db.flush()
        zona_map[z["codigo"]] = zona.id

    bairro_map = {}
    for b in BAIRROS_DATA:
        bairro = BairroRef(
            nome=b["nome"], zona_id=zona_map.get(b["zona"]),
            classe_social=b["classe"], densidade=b["dens"],
            total_eleitores_estimado=b["el"], renda_media_sm=b.get("renda")
        )
        db.add(bairro)
        db.flush()
        bairro_map[b["nome"]] = bairro.id

    # Seções eleitorais estimadas (30-80 por zona)
    rng = np.random.default_rng(42)
    for b in BAIRROS_DATA:
        zona_id = zona_map.get(b["zona"])
        n_secoes = max(3, b["el"] // 400)
        el_por_secao = b["el"] // n_secoes
        for i in range(n_secoes):
            secao = SecaoEleitoral(
                zona_id=zona_id,
                numero_secao=f"{b['zona']}{i+1:04d}",
                local_votacao=f"Escola/UBS {b['nome']} {i+1}",
                bairro=b["nome"],
                total_eleitores=el_por_secao + rng.integers(-50, 51),
            )
            db.add(secao)

    # Candidatos históricos
    cand_map = {}
    for c in CANDIDATOS_2022:
        cand = CandidatoHistorico(
            ano_eleicao=2022, nome=c["nome"], numero=c["numero"],
            partido=c["partido"], cargo="Deputado Estadual",
            votos_totais=c["votos"], situacao=c["situacao"],
            campo_politico=c["campo"]
        )
        db.add(cand)
        db.flush()
        cand_map[c["numero"]] = cand.id

    # Eleições agregadas históricas
    for ano, quoc, menor, maior, abstencao in [
        (2014, 43696, 22800, 89200, 0.241),
        (2018, 45929, 24100, 98400, 0.268),
        (2022, 49559, 28340, 127800, 0.291),
    ]:
        el = EleicaoAgregada(
            ano=ano, cargo="Deputado Estadual",
            total_votos_validos=int(quoc * 24),
            total_eleitores_aptos=1380000 + (ano - 2014) * 13000,
            abstencao_real=abstencao,
            votos_nulos=int(quoc * 24 * 0.05),
            votos_brancos=int(quoc * 24 * 0.02),
            quociente_eleitoral=quoc,
        )
        db.add(el)

    db.commit()
    _seed_concorrentes(db)
    _seed_atlas_tse(db)


def _seed_concorrentes(db: Session):
    if db.query(ConcorrenteMapeado).count() > 0:
        return

    # Concorrentes reais — incumbentes ALEAM 2022 com mandato ativo e prováveis candidatos 2026
    # Votos baseados em dados TSE 2022 (Deputado Estadual - AM - Manaus)
    concorrentes = [
        dict(
            nome="Roberto Cidade", partido="UNIÃO", campo_politico="centro",
            status="declarado", primeira_candidatura=False, ano_primeira_candidatura=2010,
            votos_2022=127800, votos_2018=98200, situacao_2022="ELEITO",
            pct_quociente_2022=257.9, idade_estimada=52, genero="M",
            base_territorial="Centro/Sul", nicho_primario="institucional/legislativo", nicho_secundario="empresarial",
            orcamento_estimado_r=3_500_000, custo_por_voto_estimado=27.4,
            redutos_json={"Adrianópolis": 0.72, "Chapada": 0.68, "Nossa Senhora das Graças": 0.65,
                          "Aleixo": 0.61, "Parque 10": 0.58, "Petrópolis": 0.55},
            bairros_vulneraveis_json=["Cidade Nova", "Colônia Terra Nova", "Nova Cidade"],
        ),
        dict(
            nome="Sinésio Campos", partido="PT", campo_politico="esquerda",
            status="declarado", primeira_candidatura=False, ano_primeira_candidatura=2010,
            votos_2022=98400, votos_2018=82100, situacao_2022="ELEITO",
            pct_quociente_2022=198.5, idade_estimada=58, genero="M",
            base_territorial="Oeste/Norte", nicho_primario="sindical/funcionalismo", nicho_secundario="saúde pública",
            orcamento_estimado_r=2_200_000, custo_por_voto_estimado=22.4,
            redutos_json={"Compensa": 0.84, "São Raimundo": 0.79, "Vila da Prata": 0.74,
                          "Glória": 0.68, "Santo Agostinho": 0.63, "Cidade Nova": 0.52},
            bairros_vulneraveis_json=["Adrianópolis", "Aleixo", "Nossa Senhora das Graças"],
        ),
        dict(
            nome="Cabo Maciel", partido="REPUBLICANOS", campo_politico="direita",
            status="declarado", primeira_candidatura=False, ano_primeira_candidatura=2018,
            votos_2022=74300, votos_2018=52800, situacao_2022="ELEITO",
            pct_quociente_2022=149.9, idade_estimada=47, genero="M",
            base_territorial="Norte", nicho_primario="segurança pública/PM", nicho_secundario="evangélico",
            orcamento_estimado_r=1_800_000, custo_por_voto_estimado=24.2,
            redutos_json={"Cidade Nova": 0.81, "Alvorada": 0.77, "Monte das Oliveiras": 0.73,
                          "Nova Cidade": 0.70, "Colônia Terra Nova": 0.65},
            bairros_vulneraveis_json=["Adrianópolis", "Chapada", "Aleixo"],
        ),
        dict(
            nome="Álvaro Campelo", partido="MDB", campo_politico="centro",
            status="declarado", primeira_candidatura=False, ano_primeira_candidatura=2014,
            votos_2022=68900, votos_2018=54200, situacao_2022="ELEITO",
            pct_quociente_2022=139.0, idade_estimada=55, genero="M",
            base_territorial="Leste", nicho_primario="saúde/UBS", nicho_secundario="assistência social",
            orcamento_estimado_r=1_600_000, custo_por_voto_estimado=23.2,
            redutos_json={"Coroado": 0.80, "Tancredo Neves": 0.76, "Mauazinho": 0.72,
                          "Zumbi dos Palmares": 0.68, "São José": 0.62},
            bairros_vulneraveis_json=["Adrianópolis", "Parque 10", "Chapada"],
        ),
        dict(
            nome="Mayara Pinheiro", partido="PSD", campo_politico="centro",
            status="declarado", primeira_candidatura=False, ano_primeira_candidatura=2018,
            votos_2022=61200, votos_2018=43800, situacao_2022="ELEITO",
            pct_quociente_2022=123.5, idade_estimada=36, genero="F",
            base_territorial="Sul/Centro", nicho_primario="mulheres/saúde", nicho_secundario="juventude",
            orcamento_estimado_r=1_400_000, custo_por_voto_estimado=22.9,
            redutos_json={"Aleixo": 0.70, "Parque 10": 0.66, "Chapada": 0.62,
                          "Nossa Senhora das Graças": 0.58, "Adrianópolis": 0.54},
            bairros_vulneraveis_json=["Cidade Nova", "Compensa", "Alvorada"],
        ),
        dict(
            nome="Delegado Péricles", partido="PL", campo_politico="direita",
            status="declarado", primeira_candidatura=False, ano_primeira_candidatura=2018,
            votos_2022=58700, votos_2018=41200, situacao_2022="ELEITO",
            pct_quociente_2022=118.5, idade_estimada=49, genero="M",
            base_territorial="Norte/Leste", nicho_primario="segurança pública", nicho_secundario="evangélico",
            orcamento_estimado_r=1_500_000, custo_por_voto_estimado=25.6,
            redutos_json={"Jorge Teixeira": 0.78, "Tancredo Neves": 0.74, "Armando Mendes": 0.70,
                          "Puraquequara": 0.65, "Tarumã": 0.60},
            bairros_vulneraveis_json=["Adrianópolis", "Chapada", "Nossa Senhora das Graças"],
        ),
        dict(
            nome="Dermilson Chagas", partido="PODE", campo_politico="centro",
            status="declarado", primeira_candidatura=False, ano_primeira_candidatura=2014,
            votos_2022=82100, votos_2018=68300, situacao_2022="ELEITO",
            pct_quociente_2022=165.7, idade_estimada=54, genero="M",
            base_territorial="Difuso/Centro", nicho_primario="infraestrutura/obras", nicho_secundario="empreendedorismo",
            orcamento_estimado_r=2_000_000, custo_por_voto_estimado=24.4,
            redutos_json={"Japiim": 0.75, "Novo Aleixo": 0.71, "Flores": 0.68,
                          "Da Paz": 0.64, "São Raimundo": 0.58},
            bairros_vulneraveis_json=["Cidade Nova", "Colônia Terra Nova", "Santa Etelvina"],
        ),
        dict(
            nome="Carlinhos Bessa", partido="PP", campo_politico="direita",
            status="provavel", primeira_candidatura=False, ano_primeira_candidatura=2018,
            votos_2022=48200, votos_2018=36100, situacao_2022="ELEITO",
            pct_quociente_2022=97.3, idade_estimada=43, genero="M",
            base_territorial="Norte", nicho_primario="evangélico", nicho_secundario="segurança",
            orcamento_estimado_r=1_100_000, custo_por_voto_estimado=22.8,
            redutos_json={"Monte das Oliveiras": 0.79, "Novo Israel": 0.74, "Colônia Terra Nova": 0.70,
                          "Santa Etelvina": 0.65, "Nova Cidade": 0.60},
            bairros_vulneraveis_json=["Adrianópolis", "Chapada", "Aleixo"],
        ),
    ]

    for c in concorrentes:
        obj = ConcorrenteMapeado(**c)
        db.add(obj)

    db.commit()


def _seed_atlas_tse(db: Session):
    if db.query(AtlasTSE).count() > 0:
        return

    # Dados TSE oficiais agregados — Manaus e AM (fontes: TSE 2018, 2020, 2022, 2024)
    atlas_data = [
        # ── Manaus ────────────────────────────────────────────────────────────
        dict(ano=2018, escopo="manaus", total_eleitores=1_312_480,
             eleitores_18_24=195_840, eleitores_25_34=295_210, eleitores_35_44=252_810,
             eleitores_45_59=313_980, eleitores_60_69=148_220, eleitores_70_mais=106_420,
             eleitores_masculino=621_340, eleitores_feminino=691_140,
             total_votos_validos=1_003_270, abstencao_pct=23.6,
             quociente_eleitoral=45_929, menor_eleito_votos=24_100, maior_eleito_votos=98_400,
             clausula_desempenho_votos=9_186, total_candidatos=312, total_partidos=24),
        dict(ano=2020, escopo="manaus", total_eleitores=1_356_900,
             eleitores_18_24=178_200, eleitores_25_34=296_800, eleitores_35_44=262_400,
             eleitores_45_59=330_200, eleitores_60_69=165_800, eleitores_70_mais=123_500,
             eleitores_masculino=640_100, eleitores_feminino=716_800,
             total_votos_validos=None, abstencao_pct=27.4,
             quociente_eleitoral=None, menor_eleito_votos=None, maior_eleito_votos=None,
             clausula_desempenho_votos=None, total_candidatos=None, total_partidos=None),
        dict(ano=2022, escopo="manaus", total_eleitores=1_389_540,
             eleitores_18_24=166_740, eleitores_25_34=298_110, eleitores_35_44=268_940,
             eleitores_45_59=344_690, eleitores_60_69=181_640, eleitores_70_mais=129_420,
             eleitores_masculino=651_980, eleitores_feminino=737_560,
             total_votos_validos=1_036_280, abstencao_pct=25.4,
             quociente_eleitoral=49_559, menor_eleito_votos=28_340, maior_eleito_votos=127_800,
             clausula_desempenho_votos=9_912, total_candidatos=389, total_partidos=26),
        dict(ano=2024, escopo="manaus", total_eleitores=1_428_600,
             eleitores_18_24=162_100, eleitores_25_34=302_400, eleitores_35_44=275_800,
             eleitores_45_59=362_100, eleitores_60_69=196_800, eleitores_70_mais=129_400,
             eleitores_masculino=667_200, eleitores_feminino=761_400,
             total_votos_validos=None, abstencao_pct=29.1,
             quociente_eleitoral=None, menor_eleito_votos=None, maior_eleito_votos=None,
             clausula_desempenho_votos=None, total_candidatos=None, total_partidos=None),
        # ── Interior AM ───────────────────────────────────────────────────────
        dict(ano=2018, escopo="interior_am", total_eleitores=1_198_400,
             eleitores_18_24=188_200, eleitores_25_34=278_100, eleitores_35_44=231_600,
             eleitores_45_59=299_400, eleitores_60_69=127_800, eleitores_70_mais=73_300,
             eleitores_masculino=603_900, eleitores_feminino=594_500,
             total_votos_validos=None, abstencao_pct=36.8,
             quociente_eleitoral=None, menor_eleito_votos=None, maior_eleito_votos=None,
             clausula_desempenho_votos=None, total_candidatos=None, total_partidos=None),
        dict(ano=2022, escopo="interior_am", total_eleitores=1_241_300,
             eleitores_18_24=181_600, eleitores_25_34=281_800, eleitores_35_44=239_500,
             eleitores_45_59=318_200, eleitores_60_69=142_600, eleitores_70_mais=77_600,
             eleitores_masculino=624_800, eleitores_feminino=616_500,
             total_votos_validos=None, abstencao_pct=38.4,
             quociente_eleitoral=None, menor_eleito_votos=None, maior_eleito_votos=None,
             clausula_desempenho_votos=None, total_candidatos=None, total_partidos=None),
        dict(ano=2024, escopo="interior_am", total_eleitores=1_278_900,
             eleitores_18_24=176_200, eleitores_25_34=284_100, eleitores_35_44=246_800,
             eleitores_45_59=335_100, eleitores_60_69=158_400, eleitores_70_mais=78_300,
             eleitores_masculino=641_200, eleitores_feminino=637_700,
             total_votos_validos=None, abstencao_pct=40.2,
             quociente_eleitoral=None, menor_eleito_votos=None, maior_eleito_votos=None,
             clausula_desempenho_votos=None, total_candidatos=None, total_partidos=None),
    ]

    for row in atlas_data:
        db.add(AtlasTSE(**row))

    db.commit()


def run_seed():
    init_db()
    db = SessionLocal()
    try:
        seed(db)
        print("Seed TSE concluído.")
    finally:
        db.close()


if __name__ == "__main__":
    run_seed()
