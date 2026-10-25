#!/usr/bin/env python3
"""Auditoria de uso: mede quanto da casa está PARADO e cobra conserto.

POR QUE EXISTE
--------------
Em 25/10/2026 o dono disse: "aposto que vocês nem usam 10% de tudo que temos". Estava certo:
23 funções órfãs, 1.991 motores no censo com 12 usados (0,6%), 32 workflows parados pela
cota e uma conta de e-mail inteira sem uso. Nada disso aparecia em lugar nenhum — o
desperdício era invisível.

Este script torna o desperdício VISÍVEL e recorrente. Toda semana ele mede:

  1. funções do comum.py que ninguém chama (código morto)
  2. robôs: quantos rodam de fato, quantos existem parados
  3. motores: quantos a cadeia usa x quantos o censo conhece
  4. segredos: quais estão gravados mas nenhum workflow usa
  5. comandos do chat: quantos estão no menu

E grava em MEMORIA/uso-da-casa.json + escreve o resumo num issue do repositório privado.
O número nunca sobe sozinho: se ficar pior, aparece na semana seguinte.
"""
import json
import os
import re
import sys

import comum as C

ARQ = "MEMORIA/uso-da-casa.json"
REPO_PUBLICO = "motor"
REPO_PRIVADO = "agente"


def _ler(caminho):
    try:
        with open(caminho, encoding="utf-8", errors="replace") as f:
            return f.read()
    except Exception:
        return ""


def funcoes_orfas():
    """Funções definidas em comum.py que nenhum outro arquivo referencia."""
    comum = _ler("comum.py")
    if not comum:
        return 0, 0, []
    outros = ""
    for nome in ("responder.py", "varrer.py", "casa.py", "dados.py", "banco.py",
                 "motor_local.py", "rodizio.py", "colher-catalogo.py", "auditoria-uso.py",
                 "sentinela.py", "checkup.py", "relatorio.py", "estudo.py", "oficina.py",
                 "digestao.py", "autocritica.py", "espelho.py", "rotina.py", "boletim.py",
                 "inspire.py", "manutencao.py", "prova-limite.py", "testar-motores.py"):
        outros += _ler(nome)
    funcs = re.findall(r"^def ([a-zA-Z_][a-zA-Z0-9_]*)", comum, re.M)
    ref = set(re.findall(r"\b(?:C|comum)\.([a-zA-Z_][a-zA-Z0-9_]*)", outros))
    ref |= set(re.findall(r"\b([a-zA-Z_][a-zA-Z0-9_]*)\s*\(", outros))
    internas = set(re.findall(r"(?<!def )\b([a-zA-Z_][a-zA-Z0-9_]*)\s*\(", comum))
    orfas = [f for f in funcs if f not in ref and f not in internas]
    return len(funcs), len(orfas), orfas


def robos_por_repo():
    """Quantos workflows cada repositório tem e quantos estão ativos."""
    saida = {}
    for repo in (REPO_PUBLICO, REPO_PRIVADO):
        try:
            fluxos = C.gh("GET", f"/repos/reboclbrank-max/{repo}/actions/workflows").get("workflows", [])
            ativos = [f for f in fluxos if f.get("state") == "active"]
            saida[repo] = {"total": len(fluxos), "ativos": len(ativos),
                           "inativos": len(fluxos) - len(ativos),
                           "nomes_inativos": [f["name"] for f in fluxos if f.get("state") != "active"]}
        except Exception as e:
            saida[repo] = {"erro": str(e)[:120]}
    return saida


def motores_em_uso():
    """Quantos motores a cadeia usa x quantos o censo conhece."""
    try:
        censo = json.loads(C.ler_remoto("MEMORIA/motores-catalogo.json", "[]") or "[]")
    except Exception:
        censo = []
    try:
        testados = json.loads(C.ler_remoto("MEMORIA/catalogo-testado.json", "{}") or "{}")
    except Exception:
        testados = {}
    try:
        aprovados = json.loads(C.ler_remoto("MEMORIA/motores-openai.json", "[]") or "[]")
    except Exception:
        aprovados = []
    comum = _ler("comum.py")
    citados = [m for m in censo if isinstance(m, str) and m in comum]
    return {"censo": len(censo), "citados_no_codigo": len(citados),
            "testados_no_desafio": len(testados.get("testados", [])),
            "aprovados_sem_chave": len(aprovados)}


def segredos_sem_uso():
    """Segredos gravados no motor que nenhum workflow referencia."""
    try:
        segredos = C.gh("GET", f"/repos/reboclbrank-max/{REPO_PUBLICO}/actions/secrets").get("secrets", [])
    except Exception as e:
        return {"erro": str(e)[:100]}
    workflows = ""
    pasta = os.path.join(".github", "workflows")
    if os.path.isdir(pasta):
        for nome in os.listdir(pasta):
            if nome.endswith((".yml", ".yaml")):
                workflows += _ler(os.path.join(pasta, nome))
    sem_uso = [s["name"] for s in segredos if s["name"] not in workflows]
    return {"gravados": len(segredos), "sem_uso": len(sem_uso), "quais": sem_uso}


def comandos_do_chat():
    fonte = _ler("responder.py")
    m = re.search(r"comandos = \((.*?)\n        \)", fonte, re.S)
    return m.group(1).count('(r"^') if m else 0


def main():
    print("=" * 70)
    print(f"AUDITORIA DE USO — {C.agora().isoformat()}")
    print("=" * 70)

    total_funcs, orfas_n, orfas = funcoes_orfas()
    robos = robos_por_repo()
    motores = motores_em_uso()
    segredos = segredos_sem_uso()
    comandos = comandos_do_chat()

    print(f"\nfunções no comum.py: {total_funcs} | órfãs: {orfas_n}")
    if orfas:
        print("  órfãs:", ", ".join(orfas[:12]))
    print(f"\ncomandos no chat: {comandos}")
    for repo, dados in robos.items():
        if "erro" in dados:
            print(f"robôs {repo}: erro ({dados['erro'][:60]})")
        else:
            print(f"robôs {repo}: {dados['ativos']} ativos de {dados['total']}")
    print(f"\nmotores: censo {motores['censo']} · citados no código {motores['citados_no_codigo']}"
          f" · testados {motores['testados_no_desafio']} · aprovados sem chave {motores['aprovados_sem_chave']}")
    if "gravados" in segredos:
        print(f"segredos: {segredos['gravados']} gravados · {segredos['sem_uso']} sem uso")
        if segredos.get("quais"):
            print("  sem uso:", ", ".join(segredos["quais"][:10]))

    # nota de aproveitamento: média simples dos quatro eixos medíveis
    notas = []
    if total_funcs:
        notas.append((total_funcs - orfas_n) / total_funcs)
    ativos = robos.get(REPO_PUBLICO, {}).get("ativos", 0)
    total_robos = sum(d.get("total", 0) for d in robos.values() if "total" in d)
    if total_robos:
        notas.append(ativos / total_robos)
    if motores["censo"]:
        notas.append(min(1.0, (motores["citados_no_codigo"] + motores["aprovados_sem_chave"])
                         / max(1, motores["citados_no_codigo"] + 20)))
    if segredos.get("gravados"):
        notas.append((segredos["gravados"] - segredos["sem_uso"]) / segredos["gravados"])
    aproveitamento = round(100 * sum(notas) / len(notas)) if notas else None

    resumo = {
        "quando": C.agora().isoformat(),
        "aproveitamento_pct": aproveitamento,
        "funcoes": {"total": total_funcs, "orfas": orfas_n, "quais": orfas},
        "robos": robos,
        "motores": motores,
        "segredos": segredos,
        "comandos_no_chat": comandos,
    }
    try:
        C.escrever_remoto(ARQ, json.dumps(resumo, ensure_ascii=False, indent=1),
                          "auditoria: uso da casa")
        print(f"\ngravado em {ARQ}")
    except Exception as e:
        print(f"não gravei: {e}")

    print("\n" + "=" * 70)
    print(f"APROVEITAMENTO MEDIDO: {aproveitamento}% dos eixos (código, robôs, motores, segredos)")
    print("=" * 70)

    # relatório no privado, para ficar no histórico
    linhas = [f"### Auditoria de uso — {C.agora().strftime('%d/%m/%Y %H:%M')} UTC", "",
              f"**Aproveitamento medido: {aproveitamento}%**", "",
              f"- funções: {total_funcs} (órfãs: {orfas_n})",
              f"- comandos do chat: {comandos}"]
    for repo, d in robos.items():
        if "erro" not in d:
            linhas.append(f"- robôs {repo}: {d['ativos']}/{d['total']} ativos")
    linhas.append(f"- motores: censo {motores['censo']} · testados {motores['testados_no_desafio']}"
                  f" · aprovados {motores['aprovados_sem_chave']}")
    if "gravados" in segredos:
        linhas.append(f"- segredos: {segredos['gravados']} · sem uso: {segredos['sem_uso']}")
    if orfas:
        linhas.append(f"- órfãs: {', '.join(orfas[:8])}")
    try:
        issue = C.gh("POST", f"/repos/reboclbrank-max/{REPO_PRIVADO}/issues",
                     {"title": f"[uso] {aproveitamento}% — auditoria semanal",
                      "body": "\n".join(linhas)})
        print(f"relatório postado: issue #{issue.get('number')}")
    except Exception as e:
        print(f"não postei o relatório: {str(e)[:120]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
