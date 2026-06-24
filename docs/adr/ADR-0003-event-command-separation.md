# ADR-0003: Event and Command Separation (CQRS) & In-Memory Messaging

## Status
Accepted

## Context
As GQOS scales, components (e.g., Risk, Execution, State) must communicate. Direct coupling via method calls creates a rigid, untestable monolith. We need a messaging architecture to decouple components. 

## Alternatives Considered

1. **Mediator Pattern**
   - *Pros*: Centralized communication, simple.
   - *Cons*: Usually treats all messages the same. Does not strongly enforce the difference between a "Fact" (Event) and an "Intent" (Command). It easily devolves into a God Object that knows too much business logic.
2. **Actor Model**
   - *Pros*: Excellent for massive concurrency and isolated state.
   - *Cons*: High cognitive load. Tracing message paths becomes difficult without specialized tooling. Overkill for the Foundation phase.
3. **External Message Queue (Kafka / RabbitMQ / Redis)**
   - *Pros*: Distributed by default, highly scalable, persistent.
   - *Cons*: Drastically increases operational complexity. Replay engine determinism is extremely difficult to guarantee across network partitions. Violates "Simplicity before sophistication."
4. **Local Event/Command Bus Separation (CQRS-lite)**
   - *Pros*: Strongly typed contracts. Explicitly defines 1-to-1 Commands (Intents) and 1-to-N Events (Facts). Guarantees deterministic FIFO ordering for Replay capability. Extremely fast (in-memory).
   - *Cons*: Does not natively distribute across machines (which we do not need yet).

## Decision
We choose **Local Event/Command Bus Separation**.
- **Commands**: Handled by exactly one handler. Represents intent. E.g. `UpdateStateCommand`.
- **Events**: Handled by zero or many subscribers. Represents past facts. E.g. `StateUpdatedEvent`.
- **Envelope/Payload**: All messages are wrapped in a generic `MessageEnvelope` containing `MessageID`, `TraceID`, `CorrelationID`, etc.
- **Immutability**: All messages are frozen dataclasses.

## Subscriber Exception Policy
If an Event has 3 subscribers, and Subscriber 1 throws an Exception:
**Decision**: The Exception is caught, logged as an Error, and the dispatch **continues** to Subscriber 2 and 3.
*Reasoning*: Events are facts that have already happened. One subscriber failing to process the fact should not crash the entire publication pipeline, nor should it abort the state change that already occurred. The failing subscriber's state must be handled independently (e.g., circuit breaker).

For Commands, if the Handler throws an Exception, it is propagated back to the Caller immediately, as the intent has failed.

## Consequences
- Routing is extremely fast (<10 µs).
- Deterministic Replay is possible due to strict FIFO ordering in the in-memory queue.
- Re-architecting to a distributed system in the future will only require swapping the `LocalEventBus` with a `KafkaEventBus` behind the `IEventBus` interface.
