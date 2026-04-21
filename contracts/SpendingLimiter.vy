# @version ^0.4.0

struct Limit:
    per_tx: uint256
    daily: uint256

limits: public(HashMap[address, Limit])
spent_today: public(HashMap[address, uint256])


@external
def set_limits(agent: address, per_tx: uint256, daily: uint256):
    self.limits[agent] = Limit({per_tx: per_tx, daily: daily})


@external
def check_and_record_spend(agent: address, amount: uint256):
    current: Limit = self.limits[agent]
    assert amount <= current.per_tx, "per-tx limit exceeded"
    assert self.spent_today[agent] + amount <= current.daily, "daily limit exceeded"
    self.spent_today[agent] += amount

