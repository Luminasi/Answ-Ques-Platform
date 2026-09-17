# ===== 记忆功能测试（非流式，只显示答案） =====
# 用法: 先启动服务 (py -3.11 -m rag_service)，再运行本脚本
$OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$base = "http://127.0.0.1:8001"

function Ask-Question {
    param([string]$q, [int]$cid = 0)
    $body = @{ question = $q; stream = $false }
    if ($cid -gt 0) { $body.conversation_id = $cid }
    $r = Invoke-WebRequest -Uri "$base/api/answer" -Method Post -Body ($body | ConvertTo-Json) `
         -ContentType "application/json; charset=utf-8" -UseBasicParsing
    $bytes = $r.RawContentStream.ToArray()
    $j = [System.Text.Encoding]::UTF8.GetString($bytes) | ConvertFrom-Json
    Write-Host ""
    Write-Host ">>> $q"
    Write-Host $j.answer
    Write-Host "[引用] $(($j.sources | ForEach-Object { "$($_.rank).$($_.source)" }) -join '  ')"
}

# 1. 新建会话
$c = Invoke-RestMethod -Uri "$base/api/conversations" -Method Post -Body '{}' -ContentType "application/json"
$cid = $c.id
Write-Host "=== 新建会话 id=$cid（stream=false 非流式）==="

# 2. 第一轮：定主题
Ask-Question -q "列表和元组有什么区别？" -cid $cid

# 3. 第二轮：指代追问，验证记住"元组"
Ask-Question -q "那它能修改吗？" -cid $cid

# 4. 第三轮：再追问，验证"它"被消解为元组
Ask-Question -q "它和字典比，谁更适合当键？" -cid $cid

# 5. 查历史（同样按 UTF-8 手动解码，避免乱码）
$hr = Invoke-WebRequest -Uri "$base/api/conversations/$cid/messages" -UseBasicParsing
$h = [System.Text.Encoding]::UTF8.GetString($hr.RawContentStream.ToArray()) | ConvertFrom-Json
Write-Host ""
Write-Host "=== 会话历史（共 $($h.messages.Count) 条消息）==="
$h.messages | ForEach-Object {
    $citations = if ($_.citations) { " [引用x$($_.citations.Count)]" } else { "" }
    $preview = $_.content
    if ($preview.Length -gt 60) { $preview = $preview.Substring(0, 60) + "..." }
    Write-Host ("  {0,-9}: {1}{2}" -f $_.role, $preview, $citations)
}
Write-Host ""
Write-Host "=== 测试完成 ==="
