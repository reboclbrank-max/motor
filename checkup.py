"""Checkup de saude dos motores — IDEIA DA PROPRIA ASSISTENTE (turno autonomo 11/10:
"precisam de health-check continuo"). A cada 4h da um ping barato em cada motor da cadeia
e atualiza o diagnostico: motor morto cai pro FIM da fila por 30 min (janela que o proprio
checkup renova). Escreve MEMORIA/saude-motores.json (resumo legivel pra ela e pro diario)."""
import json
import time

import comum


def main():
    provedores = [p for p in comum.montar_provedores() if not p.get("so_comite")]
    diag = comum.ler_diagnostico()
    estados = diag.get("provedores", {})
    resumo = []
    for p in provedores:
        probe = dict(p, timeout=25)
        t0 = time.time()
        ok, ms, erro = False, 0, ""
        try:
            texto = comum._chamar_provedor(probe, [{"role": "user", "content": "ping"}], "")
            ms = int((time.time() - t0) * 1000)
            ok = bool(texto and texto.strip())
            if not ok:
                erro = "conteudo vazio"
        except Exception as e:
            ms = int((time.time() - t0) * 1000)
            erro = str(e)[:180]
        antigo = estados.get(p["id"], {})
        novo = {"ok": ok, "testado": comum.agora().isoformat(), "ms_ultimo": ms,
                "ok_total": int(antigo.get("ok_total") or 0) + (1 if ok else 0),
                "falhas_total": int(antigo.get("falhas_total") or 0) + (0 if ok else 1),
                "modelos": p.get("modelos") or [p.get("modelo")]}
        if not ok:
            novo["erro"] = erro
        estados[p["id"]] = novo
        resumo.append({"nome": p["nome"], "ok": ok, "ms": ms})
        print(("OK " if ok else "X ") + p["nome"] + f" ({ms} ms) " + erro[:60])
    diag["provedores"] = estados
    comum.salvar_diagnostico(diag)
    vivos = [r["nome"] for r in resumo if r["ok"]]
    mortos = [r["nome"] for r in resumo if not r["ok"]]
    saude = {"quando": comum.agora().isoformat(),
             "vivos": sum(1 for r in resumo if r["ok"]), "total": len(resumo),
             "mortos": mortos, "motores": resumo}
    try:
        comum.escrever_remoto("MEMORIA/saude-motores.json",
                              json.dumps(saude, ensure_ascii=False, indent=1),
                              "checkup: saude dos motores (ideia da Assistente)")
    except Exception as e:
        comum.log(f"saude-motores: {e}")
    vivos = [r["nome"] for r in resumo if r["ok"]]
    comum.log(f"checkup: {len(vivos)}/{len(resumo)} motores vivos")
    mortos = [r["nome"] for r in resumo if not r["ok"]]
    if not vivos:
        try:
            comum.notificar("🚨 Casa sem motores: TODOS os robôs falharam no checkup",
                            "O IP do runner pode ter a janela fechada — aguarde (a caça gira o IP) ou reconecte o Wi-Fi do servidor se persistir.")
        except Exception:
            pass
    elif len(vivos) <= 2:
        try:
            comum.notificar("⚠️ Casa quase sem motores: só " + " e ".join(vivos) + " vivos",
                            "Mortos agora: " + ", ".join(mortos[:8]) + ". Se persistir 2 checkups seguidos, vale reconectar o Wi-Fi do servidor.")
        except Exception:
            pass


if __name__ == "__main__":
    main()
