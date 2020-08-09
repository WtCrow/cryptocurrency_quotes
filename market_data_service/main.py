if __name__ == '__main__':
    from controller import Controller
    import asyncio

    controller = Controller()

    loop = asyncio.get_event_loop()
    loop.create_task(controller.run())
    loop.run_forever()
