import asyncio

async def silent_fail():
    # Bug: This coroutine is never awaited, but it might cause issues on loop shutdown
    # or just be a very non-obvious reason for failure if it was supposed to do something critical.
    # Actually, let's make it more explicit.
    await asyncio.sleep(0.1)
    raise ValueError("Silent async failure")

def main():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        # We create the task but don't await it or gather it.
        # Then we exit. The loop might report unhandled exceptions.
        loop.create_task(silent_fail())
        print("Starting event loop...")
        # Simulate some work
        loop.run_until_complete(asyncio.sleep(0.2))
        print("Loop finished.")
    finally:
        loop.close()

if __name__ == "__main__":
    main()
