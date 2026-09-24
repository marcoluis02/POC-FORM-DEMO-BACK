import pytest

from app.core.unit_of_work import UnitOfWork


class RecordingSession:
    """Sesión falsa que solo anota qué se le pidió."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    async def commit(self) -> None:
        self.calls.append("commit")

    async def rollback(self) -> None:
        self.calls.append("rollback")

    async def close(self) -> None:
        self.calls.append("close")


@pytest.fixture
def session() -> RecordingSession:
    return RecordingSession()


async def test_commit_y_cierre_cuando_todo_sale_bien(session):
    async with UnitOfWork(lambda: session) as uow:
        await uow.commit()

    assert session.calls == ["commit", "close"]


async def test_rollback_y_cierre_si_algo_falla(session):
    with pytest.raises(RuntimeError):
        async with UnitOfWork(lambda: session):
            raise RuntimeError("fallo a mitad de la operación")

    assert session.calls == ["rollback", "close"]


async def test_sin_commit_no_se_guarda_nada(session):
    async with UnitOfWork(lambda: session):
        pass

    assert session.calls == ["close"]
