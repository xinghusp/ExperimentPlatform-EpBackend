/**
 * 简化版的 Guacamole WebSocket 隧道实现
 */
var GuacamoleWebSocketTunnel = function(url) {

    /**
     * 隧道的WebSocket连接对象
     * @private
     */
    var socket = null;

    /**
     * 回调处理函数
     */
    this.onstatechange = null;
    this.oninstruction = null;

    /**
     * 状态常量
     */
    this.State = {
        CONNECTING: 0,
        OPEN: 1,
        CLOSED: 2
    };

    /**
     * 当前状态
     */
    var currentState = this.State.CONNECTING;

    /**
     * 设置当前状态
     */
    function setState(state) {
        if (currentState !== state) {
            currentState = state;
            if (tunnel.onstatechange)
                tunnel.onstatechange(currentState);
        }
    }

    /**
     * 实现发送函数
     */
    this.sendMessage = function(elements) {

        // 如果未连接则抛出错误
        if (currentState !== this.State.OPEN)
            throw new Error("WebSocket隧道未连接");

        // 构建Guacamole协议消息
        var message = "";
        for (var i=0; i<elements.length; i++) {
            message += elements[i].length + "." + elements[i];
            if (i < elements.length-1)
                message += ",";
        }
        message += ";";

        // 发送消息
        socket.send(message);
    };

    /**
     * 实现关闭函数
     */
    this.disconnect = function() {
        if (socket) {
            socket.close();
            socket = null;
        }
    };

    /**
     * 从Guacamole协议中解析指令
     */
    function parseInstruction(str) {
        var instruction = [];
        var elementStart = 0;
        var elementEnd;
        var elements = str.split(',');

        for (var i=0; i<elements.length; i++) {
            var element = elements[i];
            var dot = element.indexOf('.');
            var length = parseInt(element.substring(0, dot));
            var content = element.substring(dot+1, dot+length+1);
            instruction.push(content);
        }

        return instruction;
    }

    /**
     * 隧道引用，用于回调
     */
    var tunnel = this;

    /**
     * 连接到指定URL
     */
    this.connect = function(data) {
        // 初始化WebSocket
        socket = new WebSocket(url);

        socket.binaryType = "arraybuffer";

        socket.onopen = function(event) {
            setState(tunnel.State.OPEN);
        };

        socket.onclose = function(event) {
            setState(tunnel.State.CLOSED);
        };

        socket.onerror = function(event) {
            setState(tunnel.State.CLOSED);
        };

        socket.onmessage = function(event) {
            var message;

            // 获取消息内容
            if (event.data instanceof ArrayBuffer)
                message = new TextDecoder("UTF-8").decode(event.data);
            else
                message = event.data;

            // 处理可能包含多条指令的消息
            var instructions = message.split(';');
            for (var i=0; i<instructions.length; i++) {
                if (instructions[i].length > 0) {
                    var instruction = parseInstruction(instructions[i]);
                    if (tunnel.oninstruction)
                        tunnel.oninstruction(instruction[0], instruction.slice(1));
                }
            }
        };
    };
};