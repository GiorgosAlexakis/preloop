# monitor.py
import asyncio
import nats
import os


async def main():
    nats_url = os.getenv("NATS_URL", "nats://localhost:4222")
    nc = await nats.connect(nats_url)
    js = nc.jetstream()

    stream_name = "tasks"
    consumer_name = "worker-group"

    print(
        f"Monitoring stream '{stream_name}' and consumer '{consumer_name}'. Press Ctrl+C to exit."
    )

    while True:
        try:
            stream_info = await js.stream_info(stream_name)
            consumer_info = await js.consumer_info(stream_name, consumer_name)

            pending = stream_info.state.messages
            in_progress = consumer_info.num_ack_pending

            print(
                f"\rQueue Status | Pending: {pending} | In-Progress: {in_progress}  ",
                end="",
            )

            await asyncio.sleep(1)

        except nats.errors.NotFoundError:
            print(
                f"Stream '{stream_name}' or consumer '{consumer_name}' not found. Waiting..."
            )
            await asyncio.sleep(2)
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"\nAn error occurred: {e}")
            break

    print("\nMonitor stopped.")
    await nc.close()


if __name__ == "__main__":
    asyncio.run(main())
