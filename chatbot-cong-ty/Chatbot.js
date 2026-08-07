        // Tạo UUID
        const create_UUID = () => {
            let sender = null;
            try {
                const dt = new Date().getTime();
                sender = 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
                    const r = (dt + Math.random() * 16) % 16 | 0;
                    return (c === 'x' ? r : (r & 0x3 | 0x8)).toString(16);
                });
            } catch (err) {
                console.error("Error creating UUID:", err);
            }
            return sender;
        };

        // Hàm triggerNewFormFromTab
        function triggerNewFormFromTab(tabTitle, callback) {
            try {
                var tabPanel = $('#main-tab-container').tabs('getTab', tabTitle);
                if (!tabPanel) return console.warn('⚠️ Không tìm thấy tab:', tabTitle);

                var iframe = $('iframe', tabPanel)[0];
                if (!iframe) return console.warn('⚠️ Không tìm thấy iframe trong tab:', tabTitle);

                var iframeDoc = () => iframe.contentDocument || iframe.contentWindow.document;

                var doClickNew = () => {
                    try {
                        var doc = iframeDoc();
                        var newButton = doc.getElementById("ctl00_SSELIB_MainReport_ToolbarButton_New");

                        if (newButton) {
                            newButton.click();
                            console.log("✅ Đã bấm nút Mới trong tab:", tabTitle);

                            if (typeof callback === 'function') {
                                // Gọi callback sau 800ms để đảm bảo form chuyển trạng thái
                                setTimeout(() => callback(doc), 800);
                            }
                        } else {
                            console.warn("⚠️ Không tìm thấy nút Mới trong iframe.");
                        }
                    } catch (err) {
                        console.error("❌ Lỗi khi truy cập iframe:", err);
                    }
                };

                if (iframe.contentDocument.readyState !== 'complete') {
                    iframe.onload = doClickNew;
                } else {
                    doClickNew();
                }

            } catch (err) {
                console.error("❌ Lỗi khi trigger form:", err);
            }
        }

        function fillFormFieldsFromIframe(doc, { mavattu = '', tenvattu = '', donvitinh = '' }) {
            try {
                const ma_vt_input = doc.getElementById('ctl00_SSELIB_MainReport_dirExtender_form_ma_vt');
                const ten_vt_input = doc.getElementById('ctl00_SSELIB_MainReport_dirExtender_form_ten_vt');
                const dvt_input = doc.getElementById('ctl00_SSELIB_MainReport_dirExtender_form_dvt');

                if (ma_vt_input) {
                    ma_vt_input.value = mavattu;
                    ma_vt_input.dispatchEvent(new Event('blur'));
                }
                if (ten_vt_input) {
                    ten_vt_input.value = tenvattu;
                    ten_vt_input.dispatchEvent(new Event('blur'));
                }
                if (dvt_input) {
                    dvt_input.value = donvitinh;
                    dvt_input.dispatchEvent(new Event('blur'));
                }

                console.log("✅ Đã tự động điền thông tin vật tư vào form.");
            } catch (err) {
                console.error("❌ Lỗi khi điền dữ liệu:", err);
            }
        }

        // Thêm chatbot HTML vào body (icon + box là 2 element độc lập)
        if (!document.getElementById('chatbot-icon')) {
            document.body.insertAdjacentHTML('beforeend', `
                <div id="chatbot-icon">
                    <img src="https://storage-ic.icenter.ai/smartbot-v2/chatbot_images/12282023/dc64a85b-9c28-4f73-ad3f-81025ab81833.png" alt="Chatbot">
                </div>
                <div id="chatbot-box">
                    <div id="chatbot-header">
                        <button type="button" id="chatbot-reset" onclick="resetChat()" title="Cuộc hội thoại mới">
                            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="1 4 1 10 7 10"></polyline><path d="M3.51 15a9 9 0 1 0 .49-3.51"></path></svg>
                        </button>
                        <button type="button" id="chatbot-close" onclick="closeChatbox()" title="Đóng">&times;</button>
                        <h3>🤖 Trợ Lý ERP</h3>
                        <p>Hỏi bất cứ điều gì về nghiệp vụ</p>
                    </div>
                    <div id="chatbot-messages">
                        <div class="message bot">
                            Xin chào! Tôi là trợ lý AI của SSE. Bạn cần hỏi gì?
                            <div class="timestamp">${new Date().toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' })}</div>
                        </div>
                    </div>
                    <div id="chatbot-input">
                        <div class="input-group">
                            <input type="text" id="user-input" placeholder="Nhập câu hỏi..." onkeypress="if(event.key==='Enter') sendMessage()">
                            <button type="button" class="send-btn" onclick="sendMessage()" title="Gửi">
                                <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>
                            </button>
                        </div>
                    </div>
                </div>
            `);
        }

        // Toggle mở/đóng chatbox với animation
        function openChatbox() {
            const box = document.getElementById('chatbot-box');
            box.classList.remove('is-closing');
            box.classList.add('is-open');
            setTimeout(() => document.getElementById('user-input').focus(), 350);
        }
        function closeChatbox() {
            const box = document.getElementById('chatbot-box');
            box.classList.remove('is-open');
            box.classList.add('is-closing');
            box.addEventListener('animationend', () => {
                box.classList.remove('is-closing');
            }, { once: true });
        }

        const chatbotIcon = document.getElementById('chatbot-icon');
        if (chatbotIcon) {
            chatbotIcon.addEventListener('click', () => {
                const box = document.getElementById('chatbot-box');
                if (box.classList.contains('is-open')) {
                    closeChatbox();
                } else {
                    openChatbox();
                }
            });
        }

        // Click bên ngoài chatbox để đóng (giống modal)
        document.addEventListener('click', function(e) {
            const box = document.getElementById('chatbot-box');
            const icon = document.getElementById('chatbot-icon');
            if (!box || !icon) return;
            if (box.classList.contains('is-open') &&
                !box.contains(e.target) &&
                !icon.contains(e.target)) {
                closeChatbox();
            }
        });

        // Reset toàn bộ lịch sử chat
        function resetChat() {
            chatContext.history = [];
            const chatBox = document.getElementById('chatbot-messages');
            chatBox.innerHTML = '';
            const welcome = document.createElement('div');
            welcome.className = 'message bot';
            const welcomeText = document.createElement('div');
            welcomeText.textContent = 'Cuộc hội thoại mới đã bắt đầu! Bạn cần hỏi gì?';
            welcome.appendChild(welcomeText);
            const ts = document.createElement('div');
            ts.className = 'timestamp';
            ts.textContent = new Date().toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' });
            welcome.appendChild(ts);
            chatBox.appendChild(welcome);
            document.getElementById('user-input').focus();
        }

        // Context của chatbot khi đưa lên llm
        let chatContext = { statistics: null, lastQuery: null, uploadedData: null, isTyping: false, history: [] };

        // FIX 1: Sanitize HTML chống XSS khi render Markdown từ AI
        function safeMarkdownRender(element, markdownText) {
            try {
                if (typeof marked !== 'undefined') {
                    const rawHtml = marked.parse(markdownText);
                    if (typeof DOMPurify !== 'undefined') {
                        element.innerHTML = DOMPurify.sanitize(rawHtml);
                    } else {
                        const safe = rawHtml.replace(/<script[\s\S]*?<\/script>/gi, '')
                                            .replace(/on\w+="[^"]*"/gi, '')
                                            .replace(/on\w+='[^']*'/gi, '');
                        element.innerHTML = safe;
                    }
                } else {
                    element.textContent = markdownText;
                }
            } catch (e) {
                element.textContent = markdownText;
            }
        }

        // FIX 2: Encode API Key sang ASCII-safe để tránh lỗi ISO-8859-1 trong HTTP header
        function safeApiKey(key) {
            try {
                return encodeURIComponent(String(key || '').trim());
            } catch (e) {
                return '';
            }
        }

        // Show typing indicator
        function showTypingIndicator() {
            const chatBox = document.getElementById('chatbot-messages');
            const typingDiv = document.createElement('div');
            typingDiv.className = 'typing-indicator';
            typingDiv.id = 'typing-indicator';
            typingDiv.innerHTML = `
                <div class="typing-dots">
                    <span></span>
                    <span></span>
                    <span></span>
                </div>
            `;
            chatBox.appendChild(typingDiv);
            chatBox.scrollTop = chatBox.scrollHeight;
            return typingDiv;
        }

        // Remove typing indicator
        function removeTypingIndicator() {
            const typingIndicator = document.getElementById('typing-indicator');
            if (typingIndicator) {
                typingIndicator.remove();
            }
        }

        async function sendMessage() {
            if (chatContext.isTyping) return;

            const input = document.getElementById('user-input');
            const sendBtn = document.querySelector('.send-btn');
            const question = input.value.trim();

            if (!question) return;

            // Disable input khi đang chờ bot trả lời
            chatContext.isTyping = true;
            sendBtn.disabled = true;
            input.disabled = true;
            input.value = '';

            // Hiển thị tin nhắn User lên giao diện
            const chatBox = document.getElementById('chatbot-messages');
            const userMessage = document.createElement('div');
            userMessage.className = 'message user';

            const userContent = document.createElement('div');
            userContent.textContent = question;
            userMessage.appendChild(userContent);

            const userTimestamp = document.createElement('div');
            userTimestamp.className = 'timestamp';
            userTimestamp.textContent = new Date().toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' });
            userMessage.appendChild(userTimestamp);

            chatBox.appendChild(userMessage);
            chatBox.scrollTop = chatBox.scrollHeight;

            // Hiển thị typing indicator
            showTypingIndicator();

            // Lấy context tab hiện tại (nếu có)
            let screenContext = 'unknown';
            try {
                const selected = $('#main-tab-container').tabs('getSelected');
                if (selected) {
                    const opts = selected.panel ? selected.panel('options') : selected;
                    if (opts && opts.title) screenContext = opts.title;
                }
            } catch (e) {
                console.warn('Không lấy được context tab:', e);
            }

            // Lưu câu hỏi vào lịch sử trước khi gọi API
            chatContext.history.push({ role: 'user', content: question });

            // Lấy tối đa 6 tin nhắn gần nhất
            const contextMessages = chatContext.history.slice(-6);

            let answer = '';
            let botContent = null;
            let botMessage = null;
            let streamCompletedNormally = false;

            try {
                // FIX: safeApiKey() tránh lỗi Header non-ISO-8859-1 trong HTTP request
                const llmRes = await fetch(window.CHATBOT_API_URL, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': 'Bearer ' + safeApiKey(window.CHATBOT_API_KEY)
                    },
                    body: JSON.stringify({
                        model: 'default',
                        messages: [
                            { role: 'system', content: 'Ngữ cảnh màn hình: ' + screenContext },
                            ...contextMessages
                        ],
                        stream: true
                    })
                });

                if (!llmRes.ok) {
                    throw new Error('Lỗi API: ' + llmRes.status);
                }

                // Ẩn typing indicator, tạo bong bóng chat bot
                removeTypingIndicator();

                botMessage = document.createElement('div');
                botMessage.className = 'message bot';

                botContent = document.createElement('div');
                botMessage.appendChild(botContent);

                const botTimestamp = document.createElement('div');
                botTimestamp.className = 'timestamp';
                botTimestamp.textContent = new Date().toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' });
                botMessage.appendChild(botTimestamp);

                chatBox.appendChild(botMessage);
                chatBox.scrollTop = chatBox.scrollHeight;

                // Đọc stream theo từng dòng
                const reader = llmRes.body.getReader();
                const decoder = new TextDecoder('utf-8');
                let buffer = '';
                let streamDone = false;

                while (true) {
                    const { done, value } = await reader.read();
                    if (done || streamDone) break;

                    buffer += decoder.decode(value, { stream: true });

                    let newlineIndex;
                    while ((newlineIndex = buffer.indexOf('\n')) >= 0) {
                        const line = buffer.slice(0, newlineIndex).trim();
                        buffer = buffer.slice(newlineIndex + 1);

                        if (!line.startsWith('data: ')) continue;

                        const dataPayload = line.slice(6).trim();
                        // FIX: Break ngay khi gặp [DONE]
                        if (dataPayload === '[DONE]') {
                            streamDone = true;
                            streamCompletedNormally = true;
                            break;
                        }

                        try {
                            const event = JSON.parse(dataPayload);
                            const chunk = event?.choices?.[0]?.delta?.content;
                            const finishReason = event?.choices?.[0]?.finish_reason;

                            if (chunk) {
                                answer += chunk;
                                safeMarkdownRender(botContent, answer);
                                chatBox.scrollTop = chatBox.scrollHeight;
                            }

                            // FIX CHO FPT / OPEN-SOURCE MODELS:
                            // Khi FPT Cloud gửi finish_reason = stop / length mà không bắn [DONE]
                            if (finishReason === 'stop' || finishReason === 'length') {
                                streamDone = true;
                                streamCompletedNormally = true;
                            }
                        } catch (e) {
                            // Bỏ qua JSON không hợp lệ
                        }
                    }
                }

                // FIX: Chỉ lưu lịch sử khi stream hoàn thành bình thường
                if (streamCompletedNormally && answer) {
                    chatContext.history.push({ role: 'assistant', content: answer });
                } else if (!streamCompletedNormally) {
                    chatContext.history.pop();
                }

                // FIX: Thêm nút Like / Dislike sau khi stream hoàn tất
                if (answer && botMessage) {
                    const feedbackActions = document.createElement('div');
                    feedbackActions.className = 'feedback-actions';

                    const likeBtn = document.createElement('button');
                    likeBtn.className = 'feedback-btn';
                    likeBtn.innerHTML = '👍';

                    const dislikeBtn = document.createElement('button');
                    dislikeBtn.className = 'feedback-btn';
                    dislikeBtn.innerHTML = '👎';

                    const currentQuestion = question;
                    const currentAnswer = answer;

                    likeBtn.onclick = (e) => {
                        e.stopPropagation();
                        sendFeedback(currentQuestion, currentAnswer, 'like');
                        feedbackActions.innerHTML = '<span style="font-size: 11px; color: #10b981; font-style: italic;">✓ Đã gửi đánh giá</span>';
                    };

                    dislikeBtn.onclick = (e) => {
                        e.stopPropagation();
                        sendFeedback(currentQuestion, currentAnswer, 'dislike');
                        feedbackActions.innerHTML = '<span style="font-size: 11px; color: #10b981; font-style: italic;">✓ Đã gửi đánh giá</span>';
                    };

                    feedbackActions.appendChild(likeBtn);
                    feedbackActions.appendChild(dislikeBtn);
                    botMessage.appendChild(feedbackActions);
                    chatBox.scrollTop = chatBox.scrollHeight;
                }

            } catch (err) {
                console.error('Chatbot error:', err);
                removeTypingIndicator();

                // Xóa câu hỏi đã push vào history để tránh lệch lịch sử
                chatContext.history.pop();

                const botErrMessage = document.createElement('div');
                botErrMessage.className = 'message bot';
                botErrMessage.textContent = '⚠️ Lỗi kết nối: ' + err.message;
                chatBox.appendChild(botErrMessage);
            } finally {
                // FIX: Đảm bảo luôn mở lại input trong mọi trường hợp
                chatContext.isTyping = false;
                sendBtn.disabled = false;
                input.disabled = false;
                input.focus();
            }
        }

        function sendFeedback(queryText, answerText, feedbackType) {
            const feedbackUrl = window.CHATBOT_API_URL.replace('/chat/completions', '/chat/feedback');
            fetch(feedbackUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': 'Bearer ' + safeApiKey(window.CHATBOT_API_KEY)
                },
                body: JSON.stringify({
                    feedback_type: feedbackType,
                    query_text: queryText,
                    assistant_answer: answerText
                })
            }).catch(err => console.error("Feedback error:", err));
        }

        // Initialize
        const senderId = create_UUID();
        console.log('Chatbot initialized with ID:', senderId);