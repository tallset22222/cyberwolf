"""Merge test-3 part-B chunks (stress + paced) per side: worst case per seam, with the pose that caused it.
Usage: test3_merge.py <dir>   -> writes <dir>/_test3_partB_{l,r}_all.json"""
import json, os, sys
d = sys.argv[1]
for side in 'lr':
    parts = [json.load(open(os.path.join(d, f'_test3_partB_{side}_{s}.json'))) for s in ('stress', 'paced')]
    out = json.loads(json.dumps(parts[0]))
    for seam in out:
        for m in ('LBS', 'DQS'):
            for part in parts[1:]:
                a, b = out[seam][m], part[seam][m]
                for kind in ('rigid_spec', 'rigid_best'):
                    for k, pk in (('max_slide_mm', 'slide_pose'), ('max_outward_mm', 'outward_pose'), ('max_inward_mm', 'inward_pose')):
                        if b[kind][k] > a[kind][k] and kind == 'rigid_spec': a[kind][k], a[kind][pk] = b[kind][k], b[kind][pk]
                    if kind == 'rigid_best' and b[kind]['bone'] == a[kind]['bone']:
                        for k, pk in (('max_slide_mm', 'slide_pose'), ('max_outward_mm', 'outward_pose'), ('max_inward_mm', 'inward_pose')):
                            if b[kind][k] > a[kind][k]: a[kind][k], a[kind][pk] = b[kind][k], b[kind][pk]
                    elif kind == 'rigid_best':
                        a[kind]['note'] = f"best bone differs between pose sets ({a[kind]['bone']} vs {b[kind]['bone']}); stress-set bone kept, paced worst values listed separately"
                        a[kind]['paced_set'] = b[kind]
                    a[kind]['overlap_needed_mm'] = round(a[kind]['max_slide_mm'] + 5, 1); a[kind]['15mm_sufficient'] = a[kind]['overlap_needed_mm'] <= 15
                wa, wb = a['weight_transfer'], b['weight_transfer']
                if wb['min_clearance_mm_of_2mm_shell'] < wa['min_clearance_mm_of_2mm_shell']:
                    wa['min_clearance_mm_of_2mm_shell'], wa['pose'] = wb['min_clearance_mm_of_2mm_shell'], wb['pose']
                wa['pokes_through'] = wa['min_clearance_mm_of_2mm_shell'] < 0
    json.dump(out, open(os.path.join(d, f'_test3_partB_{side}_all.json'), 'w'), indent=1)
print('merged', d)
