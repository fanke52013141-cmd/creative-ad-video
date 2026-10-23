"""Shared V8 sequence-review checks: status is not proof of coverage or quality."""
def check_sequence_review(review, storyboard):
    checked = review.get('checked_shots', [])
    expected = {row['shot_id'] for row in storyboard['shots']}
    if not checked or len(checked) != len(set(checked)) or set(checked) != expected:
        raise ValueError('sequence review must cover exactly every storyboard shot')
    if any(x.get('severity') in {'P0', 'P1'} for x in review.get('issues', [])):
        raise ValueError('sequence review blocks: unresolved P0/P1 issue(s)')
    for severity in ('P0', 'P1', 'P2'):
        actual = sum(x.get('severity') == severity for x in review.get('issues', []))
        declared = review.get(severity.lower() + '_count')
        if declared is not None and declared != actual:
            raise ValueError(f'sequence review {severity} count mismatch')
    if review.get('status') != 'pass':
        raise ValueError('sequence review requires revision')
    checks = [v for k, v in review.items() if k.endswith('_check_passed')]
    if any(v is False for v in checks):
        raise ValueError('sequence review has failed checks')
