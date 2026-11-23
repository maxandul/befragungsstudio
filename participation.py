"""Display historical participation definitions without changing survey results."""


def apply_participation_policy(row, policy, visible=True):
    row=dict(row,rate_mode='',rate_note='')
    if not policy or row.get('ground_ambiguous'):
        return row
    row.update(rate_mode=policy['mode'],rate_note=policy['note'],total=None,
               warning=False,leader_basis_missing=False)
    row['rate']=policy['rate'] if policy['mode']=='published' and visible else None
    return row
