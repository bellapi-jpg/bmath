"""
Seed dos dados de referência TSE no banco de dados
Zonas, bairros, histórico eleitoral, seções estimadas
"""
from sqlalchemy.orm import Session
from core.database import (
    ZonaEleitoral, BairroRef, SecaoEleitoral, CandidatoHistorico,
    ResultadoSecao, EleicaoAgregada, init_db, SessionLocal
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
    {"nome":"Candidato A (campo progressista)","numero":"123","partido":"PT","votos":82400,"situacao":"ELEITO","campo":"esquerda"},
    {"nome":"Candidato B (campo progressista)","numero":"124","partido":"PDT","votos":61200,"situacao":"ELEITO","campo":"esquerda"},
    {"nome":"Candidato C (campo progressista)","numero":"125","partido":"PSOL","votos":48900,"situacao":"ELEITO","campo":"esquerda"},
    {"nome":"Candidato D (centro)","numero":"200","partido":"MDB","votos":127800,"situacao":"ELEITO","campo":"centro"},
    {"nome":"Candidato E (campo conservador)","numero":"300","partido":"PL","votos":98400,"situacao":"ELEITO","campo":"direita"},
    {"nome":"Candidato F (campo conservador)","numero":"301","partido":"PP","votos":72100,"situacao":"ELEITO","campo":"direita"},
    {"nome":"Suplente G","numero":"302","partido":"PSD","votos":31200,"situacao":"NÃO ELEITO","campo":"centro"},
    {"nome":"Suplente H","numero":"126","partido":"REDE","votos":28340,"situacao":"NÃO ELEITO","campo":"esquerda"},
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
