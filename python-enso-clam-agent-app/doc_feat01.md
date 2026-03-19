# 功能

应用场景：
```
分析东亚地区当前的ENSO情况
MCP ---> 服务
```

当MCP调用时从`https://www.hko.gov.hk/tc/lrf/enso/enso-front.htm`拉取最新的信息，交给
Gemini 3 Flash review 模型分析结果，并返回

# 说明
- gemini API doc
https://ai.google.dev/gemini-api/docs/quickstart?hl=zh-cn

gemini api token:
```
请配置到 .env 文件中，不要写入代码或文档
```