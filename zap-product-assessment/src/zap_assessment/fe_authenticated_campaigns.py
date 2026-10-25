"""Finite campaign parameter substitution from reviewed fields and owned fixtures."""
import copy

def materialize(c,fixtures):
    result=copy.deepcopy(c);result['path']=c['path'].format_map(fixtures)
    for target,bindings in [('body','bodyBindings'),('query','queryBindings')]:
        for field,fixture in c.get(bindings,{}).items():
            if field not in c[target] or fixture not in fixtures:raise ValueError('campaign fixture missing')
            result[target][field]=fixtures[fixture]
    return result
