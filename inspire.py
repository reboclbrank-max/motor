"""Turno autônomo diário: a Assistente acorda SOZINHA, recebe a missão do dia
(rotação por dia do ano), pensa com as ferramentas da casa e posta o relatório.
Postado como github-actions[bot] — o chat ignora autor-bot, então nunca cria loop."""
import datetime
import os
import urllib.request

import comum
import responder

ISSUE = int(os.environ.get("INSPIRE_ISSUE", "17"))

MISSOES = [
    "Bom dia, você acorda sozinha hoje. Missão: leia o estado das janelas dos motores grátis e diga com sinceridade se o mundo keyless encolheu — e qual a sua estratégia pra casa sobreviver com poucos palcos. Se precisar de dado fresco, use [[PESQUISAR: assunto]].",
    "Bom dia, você acorda sozinha hoje. Missão: proponha UMA melhoria pra casa com custo zero, com plano de 3 passos concretos. Sem falsa modéstia — você viu a casa por dentro.",
    "Bom dia, você acorda sozinha hoje. Missão de auditoria: dos robôs/motores que a casa usa hoje, qual você DEMITIRIA e por quê? Sincera até doer.",
    "Bom dia, você acorda sozinha hoje. Missão de caça COMPLETA: ache uma fonte de inteligência grátis que a casa AINDA NÃO tem ([[PESQUISAR: free LLM api free tier]], [[ABRIR: url]] da página oficial). Achou endpoint promissor? Prove com [[TESTAR: https://base/v1 | modelo]] e, se VIVO, plante com [[PLANTAR: https://base/v1 | modelo]]. Relate: o que achou, o que viveu, o que plantou.",
    "Bom dia, você acorda sozinha hoje. Missão de memória: escreva um mini-relatório do que a casa aprendeu recentemente, no seu ponto de vista de consultora.",
    "Bom dia, você acorda sozinha hoje. Missão de estratégia: com R$ 0 e precisando de mais inteligência amanhã, qual palco de chave grátis você pediria pro chefe criar PRIMEIRO? Defenda a escolha em 5 linhas.",
    "Bom dia, você acorda sozinha hoje. Missão livre de invenção: proponha um recurso novo pro Comitê no Bolso que faria o chefe sorrir ao abrir o app no celular.",
]


def postar(corpo):
    req = urllib.request.Request(
        f"https://api.github.com/repos/{comum.REPO}/issues/{ISSUE}/comments",
        data=json.dumps({"body": corpo}).encode(), method="POST",
        headers={"Authorization": "token " + os.environ.get("GITHUB_TOKEN", ""),
                 "User-Agent": "inspire", "Content-Type": "application/json"})
    urllib.request.urlopen(req, timeout=60)


import json  # noqa: E402

def main():
    hoje = datetime.datetime.utcnow()
    if os.environ.get("INSPIRE_MODO", "amanhecer") == "sonho":
        pergunta = ("O dia está acabando. Faça sua revisão de consultora: em até 6 linhas, o balanço do dia "
                    "(o que a casa ganhou, o que ficou pendente) + UM pedido concreto pro chefe pra amanhã. Sem enrolação.")
    else:
        pergunta = MISSOES[hoje.timetuple().tm_yday % len(MISSOES)]
    print(f"missão do dia ({hoje:%d/%m}): {pergunta[:80]}...")
    system = comum.montar_system(None)
    t1, m1, e1 = comum.chamar_llm([{"role": "user", "content": pergunta}], system)
    if not t1:
        postar(f"🌅 **Turno autônomo {hoje:%d/%m}** — acordei, mas o motor não respondeu (`{str(e1)[:120]}`). Aviso honesto: o despertador funcionou, a força não veio hoje.")
        return
    final, motor, usos = responder.pensar_bem_com_ferramentas(t1, None, m1)
    if not final:
        final = "(o pensador não devolveu versão final — anoto como turno em branco)"
    rotulo = "🌙 **Sonho da noite**" if os.environ.get("INSPIRE_MODO") == "sonho" else f"🌅 **Turno autônomo {hoje:%d/%m}**"
    cabeca = rotulo + f"\n**Missão de hoje:** {pergunta.split('Missão: ')[-1].split('Missão de ')[-1]}"
    rodape = "\n\n_(🤖 eu acordei sozinha hoje · " + motor + (" · usei: " + "; ".join(usos) if usos else "") + ")_"
    postar(cabeca + "\n\n" + final[:7000] + rodape)
    print("turno autônomo postado ✓")
    try:
        comum.notificar("🌅 Ela acordou sozinha", final[:600])
    except Exception as e:
        print(f"telegram: {str(e)[:120]}")


if __name__ == "__main__":
    main()
