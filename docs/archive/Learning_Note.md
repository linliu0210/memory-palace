那关于 core 的一个设计上的问题是: 分拣规则 (v0.1) 是按照 if `importance >= 0.7` 进入 Core, 但是 Core 又限制只能2kb, 那 Core 到了 2kb 之后怎么办, 淘汰掉早的? 不过我认可 Core 固定大小, 或者以一个极低速度增长的设计理念, 只不过应该想办法解决这个冲突.

那其实 4.1 出生：从用户输入到 MemoryItem 这一步是agent来做的, 那agent如何自己做这么work呢? 设计一个智能识别 conversation dataset? 还是怎么办? 我把流程的开头理解为 agent 拿到一些context, 智能地调用 cli.py 的 save() 函数

4.2 就是直接识别对话了, 所以 3F 才是 agent 工作的地方,  5F 是面向人的? 