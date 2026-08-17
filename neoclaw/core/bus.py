import asyncio

#这是一个全局异步队列。，系统有两个消息生产者：用户输入，hearbeats到期任务
task_queue = asyncio.Queue()

async def emit_task(content: str):
    await task_queue.put(content)