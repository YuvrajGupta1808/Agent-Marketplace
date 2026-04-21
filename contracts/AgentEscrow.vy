# @version ^0.4.0

struct Escrow:
    buyer: address
    seller: address
    amount: uint256
    timeout: uint256
    released: bool

escrows: public(HashMap[bytes32, Escrow])


@external
def create_escrow(escrow_id: bytes32, seller: address, amount: uint256, timeout: uint256):
    assert self.escrows[escrow_id].buyer == empty(address), "escrow exists"
    self.escrows[escrow_id] = Escrow({
        buyer: msg.sender,
        seller: seller,
        amount: amount,
        timeout: timeout,
        released: False,
    })


@external
def release(escrow_id: bytes32):
    escrow: Escrow = self.escrows[escrow_id]
    assert msg.sender == escrow.buyer, "only buyer"
    assert not escrow.released, "already released"
    self.escrows[escrow_id].released = True


@external
def refund(escrow_id: bytes32):
    escrow: Escrow = self.escrows[escrow_id]
    assert block.timestamp >= escrow.timeout, "not expired"
    assert not escrow.released, "already released"
    self.escrows[escrow_id].released = True

