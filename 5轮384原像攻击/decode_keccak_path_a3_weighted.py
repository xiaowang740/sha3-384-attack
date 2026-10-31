"""Decode and validate the a3 weighted-objective model."""
import argparse
import json
from pathlib import Path

from decode_keccak_path import read_model, bits_to_int, decode_weights, format_lane_report


def decode(data, model):
    states = {**data['path_state_bits'], **data['path_c_bits'], **data['path_a_bits']}
    needed = {v for bits in states.values() for v in bits}
    needed.update(v for tr in data['round_transition_weights']
                  for box in tr['boxes'] for v in box['weight_bits'])
    needed.update(data['start_round_selector_bits'])
    missing = needed.difference(model)
    if missing:
        raise ValueError(f'model missing {len(missing)} required variables')
    starts = [i for i, v in enumerate(data['start_round_selector_bits']) if model[v]]
    if len(starts) != 1:
        raise ValueError('invalid start-round selector')
    path = {'iota_start_round': starts[0], 'explicit_final_state': 'a3'}
    for name, bits in states.items():
        if len(bits) != 800:
            raise ValueError(f'{name}: expected 800 bits')
        path[name] = [f'{bits_to_int(bits[i:i+32], model):08x}' for i in range(0, 800, 32)]
    transitions, total = decode_weights(data, model)
    weights = [tr['weight'] for tr in transitions]
    objective = sum(w * k for w, k in zip(weights, data['objective_coefficients']))
    if weights[0] > data['transition0_limit'] or objective > data['objective_limit']:
        raise ValueError(f'weight constraints violated: W0={weights[0]}, objective={objective}')
    path.update(transitions=transitions, total_weight=total,
                weighted_objective=objective, objective_limit=data['objective_limit'])
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('model', type=Path)
    parser.add_argument('--weights', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    path = decode(json.loads(args.weights.read_text(encoding='ascii')), read_model(args.model))
    args.out.write_text(json.dumps(path, indent=2) + '\n', encoding='ascii')
    report = format_lane_report(path).replace(
        'b3 -> c3 -> a3 -> b4', 'b3 -> c3 -> a3; Chi weight to b4, b4 not modeled')
    report += f"weighted_objective (2*W1+2*W2+W3): {path['weighted_objective']} <= {path['objective_limit']}\n"
    args.out.with_suffix('.lanes.txt').write_text(report, encoding='ascii')
    print(f'decoded path: {args.out}')
    print(report, end='', flush=True)


if __name__ == '__main__':
    main()
