import asyncio
from collections import defaultdict
from datetime import datetime, timezone
from typing import AsyncIterator, DefaultDict, Dict, List

from app.core.enums import AgentStatus
from app.schemas import ProgressEvent


class EventBus:
    def __init__(self) -> None:
        self._history: DefaultDict[str, List[ProgressEvent]] = defaultdict(list)
        self._subscribers: DefaultDict[str, List[asyncio.Queue]] = defaultdict(list)
        self._completed: Dict[str, bool] = {}

    async def publish(
        self,
        run_id: str,
        agent_name: str,
        status: AgentStatus,
        partial_result_summary: str,
        metadata: Dict[str, object] = None,
    ) -> ProgressEvent:
        event = ProgressEvent(
            run_id=run_id,
            agent_name=agent_name,
            status=status,
            partial_result_summary=partial_result_summary,
            timestamp=datetime.now(timezone.utc),
            metadata=metadata or {},
        )
        self._history[run_id].append(event)
        for queue in list(self._subscribers[run_id]):
            await queue.put(event)
        if event.metadata.get("terminal"):
            self._completed[run_id] = True
        return event

    async def subscribe(self, run_id: str) -> AsyncIterator[ProgressEvent]:
        queue: asyncio.Queue = asyncio.Queue()
        self._subscribers[run_id].append(queue)
        try:
            for event in self._history.get(run_id, []):
                yield event
            if self._completed.get(run_id):
                return
            while True:
                event = await queue.get()
                yield event
                if event.metadata.get("terminal"):
                    return
        finally:
            if queue in self._subscribers[run_id]:
                self._subscribers[run_id].remove(queue)

    def history(self, run_id: str) -> List[ProgressEvent]:
        return list(self._history.get(run_id, []))


event_bus = EventBus()

