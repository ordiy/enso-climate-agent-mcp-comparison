

# Step 1: initialize

curl -X POST \
  -H "Content-Type: application/json" \
  -H 'Authorization: Bearer YTZkNDBmNWUtOTgwMy00OTJjLThmZTItYjEyYzg1MmJmYjZlCg==' \
  -H "Accept: application/json, text/event-stream" \
  https://tuuai.app.n8n.cloud/mcp-test/4e5f2756-d215-4b29-878e-59662ceb7f52 \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
      "protocolVersion": "2024-11-05",
      "capabilities": {},
      "clientInfo": {"name": "curl-test", "version": "1.0"}
    }
  }'



curl -X POST https://你的n8n实例地址/rest/webhooks/test/4e5f2756-d215-4b2... \
     -H "Authorization: Bearer YTZkNDBmNWUtOTgwMy00OTJjLThmZTItYjEyYzg1MmJmYjZlCg==" \
     -H "Content-Type: application/json" \
     -d '{"event": "test", "data": "hello world"}'


   curl -X POST   https://tuuai.app.n8n.cloud/mcp-test/4e5f2756-d215-4b29-878e-59662ceb7f52 \
          -H "Authorization: Bearer YTZkNDBmNWUtOTgwMy00OTJjLThmZTItYjEyYzg1MmJmYjZlCg==" \
          -H "Content-Type: application/json" \
          -H "Accept: application/json, text/event-stream" \
     -H "Content-Type: application/json" \
     -d '{"event": "test", "data": "hello world"}'