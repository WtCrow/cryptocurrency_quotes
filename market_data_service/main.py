if __name__ == '__main__':
    from controller import Controller
    import asyncio

    contr = Controller()

    loop = asyncio.get_event_loop()
    loop.create_task(contr.run())
    loop.run_forever()
