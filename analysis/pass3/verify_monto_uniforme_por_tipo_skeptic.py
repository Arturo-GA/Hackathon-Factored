# Verificador escéptico del hallazgo 'monto_uniforme_por_tipo': ejecuta las partes a..f en orden.
# a: límites exactos y granularidad | b: uniformidad fina (1000 bins, KS, momentos, alternativa log-uniforme)
# c: eta^2/F de u dentro de ttype para 47 variables de tx/cu/pr | d: efecto cliente/producto, secuencia, repeticiones, AUC de rechazo/51/fraude
# e: K fijo vs fx diario, R2 exacto, enlaces con cp.claimed y de.event_value | f: GBM con 39 features (incluye u previa) en held-out agrupado
import runpy, sys, os
here=os.path.dirname(os.path.abspath(__file__))
parts=sys.argv[1:] or list('abcdef')
for p in parts:
    print(f'\n######## parte {p} ########', flush=True)
    runpy.run_path(os.path.join(here, f'verify_monto_uniforme_por_tipo_skeptic_{p}.py'), run_name='__main__')
