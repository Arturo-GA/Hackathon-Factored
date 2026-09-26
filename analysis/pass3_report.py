"""Genera docs/hallazgos_detalle.md a partir del resultado del workflow de agentes (3ª pasada).

Entrada: analysis/pass3/_results/<run>.json (salida del workflow; no se versiona).
Cada hallazgo trae su estado de verificación: confirmado (2 verificadores no lo refutan),
disputado (uno lo refuta), refutado, o no verificado (resultados negativos).

Uso: python analysis/pass3_report.py analysis/pass3/_results/final.json
"""
import json
import sys

sys.path.insert(0, "analysis")
from sanitize_docs import sanitize  # noqa: E402

ORDER = {"confirmado": 0, "disputado": 1, "no-verificado (negativo)": 2, "verificación falló": 3, "refutado": 4}


def main(path):
    raw = json.load(open(path, encoding="utf-8"))
    data = raw.get("result", raw)
    rounds = [r for r in (data.get("round1") or []) + (data.get("round2") or []) if r]
    findings = [f for r in rounds for f in r["findings"]]
    counts = {}
    for f in findings:
        counts[f["status"]] = counts.get(f["status"], 0) + 1

    lines = ["# Hallazgos detallados (3ª pasada: agentes + verificación adversaria)", "",
             "8 exploradores buscaron patrones (sobre todo en transacciones). Cada hallazgo de tipo "
             "`signal`/`rule` fue revisado por 2 verificadores independientes: uno lo reprodujo con su propio "
             "código y otro intentó refutarlo. Los `data_quality` se reprodujeron una vez; los `negative` "
             "(hipótesis descartadas) no se verifican. Scripts en `analysis/pass3/`.", "",
             "Estados: " + ", ".join(f"{k}: {v}" for k, v in sorted(counts.items(), key=lambda kv: ORDER.get(kv[0], 9))), ""]

    for r in rounds:
        lines += [f"## Lente: {r['lens']}", "", "| Estado | Tipo | Fuerza | Hallazgo |", "|---|---|---|---|"]
        fs = sorted(r["findings"], key=lambda f: ORDER.get(f["status"], 9))
        for f in fs:
            lines.append(f"| {f['status']} | {f['type']} | {f['strength']} | {f['title'].replace('|', '/')} |")
        lines.append("")
        for f in fs:
            correction = next((v.get("correction") for v in f.get("votes", []) if v.get("correction")), "")
            lines += [f"### {f['title']}", "",
                      f"- **Estado:** {f['status']} · **tipo:** {f['type']} · **id:** `{f['id']}`",
                      f"- **Afirmación:** {f['claim']}",
                      f"- **Evidencia:** {f['evidence']}"]
            if correction:
                lines.append(f"- **Versión corregida por el verificador:** {correction}")
            refutes = [v.get("reason", "") for v in f.get("votes", []) if v.get("refuted")]
            if refutes:
                lines.append(f"- **Objeción del verificador:** {refutes[0]}")
            lines += [f"- **Cómo usarlo:** {f['exploitation']}",
                      f"- **Reproducir:** `{f['script']}`", ""]
        if r.get("coverage"):
            lines += ["**Probado sin resultado:**", "", r["coverage"], ""]

    critic = data.get("critic") or []
    if critic:
        lines += ["## Próximos pasos propuestos por el crítico (no explorados)", ""]
        for h in critic:
            lines.append(f"- **{h['key']}**: {h['rationale']}")
        lines.append("")

    text, n = sanitize("\n".join(lines) + "\n")
    with open("docs/hallazgos_detalle.md", "w", encoding="utf-8") as fh:
        fh.write(text)
    print(f"docs/hallazgos_detalle.md: {len(findings)} hallazgos, {n} valores enmascarados")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "analysis/pass3/_results/final.json")
