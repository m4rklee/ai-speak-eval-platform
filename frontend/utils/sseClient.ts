/**
 * SSE 客户端工具类
 * 用于处理 POST 请求的流式响应
 */

export interface SSEOptions {
    onMessage: (data: any) => void
    onError?: (error: Error) => void
    onComplete?: () => void
}

export async function createPostSSE(url: string, body: any, options: SSEOptions) {
    try {
        const response = await fetch(url, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            credentials: 'include',
            body: JSON.stringify(body),
        })

        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`)
        if (!response.body) throw new Error(`Response body is null`)
        
        const reader = response.body.getReader()
        const decoder = new TextDecoder()
        let buffer = ''

        const processStream = async () => {
            try {
                while(true) {
                    const {done, value} = await reader.read()
                    if (done) {options.onComplete?.(); break}

                    // stream: true 能处理跨 chunk 的多字节字符（如中文）
                    buffer += decoder.decode(value, {stream: true})

                    // SSE 格式：每个事件以 \n\n 分隔
                    const parts = buffer.split('\n\n')
                    buffer = parts.pop() || ''

                    for (const part of parts){
                        if(!part.trim()) continue
                        const lines = part.split('\n')
                        for (const line of lines){
                            const trimmed = line.trim()
                            if (trimmed.startsWith('data:')) {
                                const jsonStr = trimmed.substring(5).trim()
                                if (jsonStr) {
                                    try {
                                        const data = JSON.parse(jsonStr)
                                        options.onMessage(data)
                                    }catch(e){
                                        console.warn('JSON解析失败，等待更多数据')
                                    }
                                }
                            }
                        }
                    }
                }
            }catch (error: any){
                options.onError?.(error)
            }
        }

        processStream()

        return {
            close: () => {reader.cancel()},
        }
    } catch(error: any){
        options.onError?.(error)
        throw error
    }
}
