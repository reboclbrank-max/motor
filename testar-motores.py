#!/usr/bin/env python3
"""Testa os motores de verdade e guarda o resultado.

POR QUE ESTE ARQUIVO EXISTE
---------------------------
Em 24/10/2026 o Chat devolveu "pare o canal com ROAS menor que 2:1" (marketing genérico)
para uma pergunta sobre números que a casa mede. Investigando, dois defeitos:

1. O teste de saúde mandava "Responda apenas: OK". Qualquer endpoint que devolva texto
   fixo passa nesse teste — inclusive um morto. Por isso 8 de 14 motores apareceram
   "vivos" em 11/10/2026 e a cadeia continuou caindo em resposta genérica.
2. Os testes rodavam do meu ambiente, e o ambiente mentiu: `models.github.ai` devolveu
   HTTP 200 com o corpo "OK" até para token inválido e caminho inexistente. Prova que
   testar HTTP 200 do meu lado não serve — só o runner do GitHub tem internet real.

Este script roda NO RUNNER, manda um DESAFIO (conta com resultado verificável e etiqueta
que o modelo é instruído a não repetir) e só marca vivo quem acerta. Também testa uma
lista de candidatos sem chave e grava os aprovados em MEMORIA/motores-openai.json, que é
o arquivo que a cadeia lê para crescer sozinha.

Nada aqui inventa número: se nenhum passar, o resultado é zero vivo e está escrito.
"""
import json
import os
import sys
import time

import comum as C

# Candidatos sem chave / com o token que já existe. Podem falhar todos — é o esperado
# de um teste honesto. Os que passarem entram na cadeia.
CANDIDATOS_PADRAO = [
    {"nome": "GitHub Models (gpt-4o-mini)", "tipo": "openai",
     "base": "https://models.github.ai/inference", "modelo": "openai/gpt-4o-mini",
     "chave": os.environ.get("PAT_MEMORIA") or "", "timeout": 45},
    {"nome": "GitHub Models (gpt-4.1-mini)", "tipo": "openai",
     "base": "https://models.github.ai/inference", "modelo": "openai/gpt-4.1-mini",
     "chave": os.environ.get("PAT_MEMORIA") or "", "timeout": 45},
    {"nome": "GitHub Models (Llama-4-Scout)", "tipo": "openai",
     "base": "https://models.github.ai/inference",
     "modelo": "meta/Llama-4-Scout-17B-16E-Instruct",
     "chave": os.environ.get("PAT_MEMORIA") or "", "timeout": 45},
    {"nome": "llm7 (default, sem chave)", "tipo": "openai",
     "base": "https://api.llm7.io/v1", "modelo": "default",
     "chave": os.environ.get("CHAVE_LLM7") or "unused", "timeout": 45},
    {"nome": "Pollinations (openai)", "tipo": "openai",
     "base": "https://text.pollinations.ai/openai", "modelo": "openai",
     "chave": "unused", "timeout": 45},
    {"nome": "Hack Club AI", "tipo": "openai",
     "base": "https://ai.hackclub.com/v1", "modelo": "qwen/qwen3-32b",
     "chave": "unused", "timeout": 45},
]


def testar_candidatos():
    """Manda o desafio para cada candidato e devolve a lista dos aprovados."""
    try:
        crus = json.loads(C.ler_remoto("MEMORIA/motores-candidatos.json", "[]") or "[]")
    except Exception:
        crus = []
    validos = [c for c in crus if isinstance(c, dict) and c.get("base") and c.get("modelo")]
    candidatos = validos or CANDIDATOS_PADRAO
    aprovados, linhas = [], []
    for cand in candidatos:
        p = {"nome": cand["nome"], "id": "cand-" + C.re.sub(r"\W+", "-", cand["nome"].lower())[:24],
             "tipo": cand.get("tipo") or "openai", "base": cand["base"],
             "chave": cand.get("chave") or "unused", "modelo": cand["modelo"],
             "modelos": [cand["modelo"]], "timeout": int(cand.get("timeout") or 45)}
        passou, ms, motivo = C.provar_motor(p, tentativas=1)
        if passou:
            linhas.append(f"✅ candidato {cand['nome']} — {ms} ms · ACERTOU o desafio")
            aprovados.append({"nome": cand["nome"], "base": cand["base"], "modelo": cand["modelo"],
                              "tipo": p["tipo"], "timeout": p["timeout"],
                              "chave": "propria" if cand.get("chave") else "unused",
                              "verificado": C.agora().date().isoformat()})
        else:
            linhas.append(f"❌ candidato {cand['nome']} — {motivo} ({ms} ms)")
    if aprovados:
        try:
            C.escrever_remoto("MEMORIA/motores-openai.json",
                              json.dumps(aprovados, ensure_ascii=False, indent=1),
                              "motores: candidatos aprovados no desafio")
        except Exception as e:
            linhas.append(f"⚠️ não consegui salvar os aprovados: {e}")
    return linhas, aprovados


def main():
    print("=" * 70)
    print(f"TESTE DE MOTORES — {C.agora().isoformat()}")
    print("Método: DESAFIO (conta com resultado verificável + etiqueta anti-eco).")
    print("Um motor só é 'vivo' se ACERTAR a conta. HTTP 200 não conta.")
    print("=" * 70)

    linhas = C.testar_provedores()
    print("\n-- motores configurados --")
    for l in linhas:
        print(l)

    print("\n-- candidatos sem chave --")
    linhas_cand, aprovados = testar_candidatos()
    for l in linhas_cand:
        print(l)

    diag = C.ler_diagnostico()
    estados = diag.get("provedores", {})
    vivos = [k for k, v in estados.items() if v.get("cerebro")]
    sem_cerebro = [k for k, v in estados.items() if v.get("cerebro") is False]

    resumo = {
        "quando": C.agora().isoformat(),
        "metodo": "desafio",
        "vivos": len(vivos),
        "sem_cerebro": len(sem_cerebro),
        "total": len(estados),
        "aprovados_sem_chave": len(aprovados),
        "detalhe": {k: {"vivo": bool(v.get("cerebro")), "ms": v.get("ms_ultimo"),
                        "erro": v.get("erro")} for k, v in estados.items()},
    }
    try:
        C.escrever_remoto("MEMORIA/saude-motores.json",
                          json.dumps(resumo, ensure_ascii=False, indent=1),
                          "motores: saúde medida por desafio")
    except Exception as e:
        print(f"⚠️ não consegui salvar a saúde: {e}")

    print("\n" + "=" * 70)
    print(f"RESULTADO: {len(vivos)} de {len(estados)} motores pensam de verdade.")
    print(f"Candidatos sem chave aprovados: {len(aprovados)}")
    if not vivos and not aprovados:
        print("NENHUM motor passou o desafio. A cadeia vai usar a análise determinística")
        print("(casa.analise) — que não inventa — e o Chat fica sem raciocínio livre.")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
