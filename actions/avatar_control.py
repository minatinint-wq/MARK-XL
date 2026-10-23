"""Validate model controls before crossing the local Qt/WebGL bridge."""
import math

def normalize_avatar_command(parameters):
    action = str(parameters.get('action', 'rotate')).lower().strip()
    if action == 'mask_lights':
        enabled = parameters.get('enabled')
        if not isinstance(enabled, bool):
            raise ValueError('enabled deve ser true ou false.')
        return {'action': 'mask_lights', 'enabled': enabled}
    if action == 'reset':
        return {'action': 'reset'}
    if action != 'rotate':
        raise ValueError('Use rotate, reset ou mask_lights para controlar o modelo 3D.')
    axis = str(parameters.get('axis', 'y')).lower().strip()
    if axis not in {'x', 'y', 'z'}:
        raise ValueError('Eixo deve ser x, y ou z.')
    value = parameters.get('degrees', 45)
    if isinstance(value, bool):
        raise ValueError('Informe o ângulo em graus.')
    degrees = float(value)
    if not math.isfinite(degrees) or abs(degrees) > 3600:
        raise ValueError('Ângulo deve ser finito, entre -3600 e 3600 graus.')
    return {'action': 'rotate', 'axis': axis, 'degrees': degrees}
