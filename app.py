from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, join_room, leave_room, send, emit
import json
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, cors_allowed_origins="*")

# 存储在线用户信息
online_users = {}
room_name = 'chat_room'

# 读取配置文件
def load_config():
    config_path = os.path.join(os.path.dirname(__file__), 'config.json')
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)

# 获取配置
config = load_config()

@app.route('/')
def index():
    return render_template('login.html')

@app.route('/chat')
def chat():
    nickname = request.args.get('nickname')
    server = request.args.get('server')
    return render_template('chat.html', nickname=nickname, server=server)

@app.route('/get_servers')
def get_servers():
    return jsonify(config['servers'])

@app.route('/check_nickname')
def check_nickname():
    nickname = request.args.get('nickname')
    is_valid = nickname not in online_users
    return jsonify({'valid': is_valid})

@socketio.on('connect')
def handle_connect():
    print('Client connected')

@socketio.on('disconnect')
def handle_disconnect():
    sid = request.sid
    # 查找断开连接的用户
    for nickname, user_info in online_users.items():
        if user_info['sid'] == sid:
            # 从在线用户列表中移除
            del online_users[nickname]
            # 通知其他用户
            emit('user_left', {'nickname': nickname, 'users': list(online_users.keys())}, room=room_name)
            leave_room(room_name, sid)
            print(f'{nickname} disconnected')
            break

@socketio.on('join')
def handle_join(data):
    nickname = data['nickname']
    sid = request.sid
    
    # 添加用户到在线列表
    online_users[nickname] = {'sid': sid}
    
    # 加入聊天室
    join_room(room_name, sid)
    
    # 通知当前用户成功加入
    emit('join_success', {'message': f'成功加入聊天室！', 'users': list(online_users.keys())})
    
    # 通知其他用户
    emit('user_joined', {'nickname': nickname, 'users': list(online_users.keys())}, room=room_name, skip_sid=sid)
    
    print(f'{nickname} joined the chat')

@socketio.on('send_message')
def handle_message(data):
    nickname = data['nickname']
    message = data['message']
    
    # 先发送用户的原始消息
    emit('receive_message', {
        'nickname': nickname,
        'message': message,
        'type': 'normal'
    }, room=room_name)
    
    # 处理@命令
    response = process_command(message, nickname)
    
    # 如果是特殊命令响应，额外发送响应消息
    if response['type'] != 'normal':
        emit('receive_message', {
            'nickname': '系统' if response['type'] == 'ai_response' else nickname,
            'message': response['message'],
            'type': response['type']
        }, room=room_name)

def process_command(message, nickname):
    # 检查是否是@命令
    if message.startswith('@'):
        parts = message.split(' ', 1)
        command = parts[0].lower()
        content = parts[1] if len(parts) > 1 else ''
        
        # 处理@奶小胖命令（与AI对话，当前返回模拟响应）
        if command == '@奶小胖':
            return {
                'message': f'[AI回复] 你好{nickname}，我是奶小胖！很高兴为你服务。',
                'type': 'ai_response'
            }
        # 处理@电影命令（电影播放，生成iframe嵌入）
        elif command == '@电影':
            # 检查是否提供了URL
            if content.strip():
                # 构建解析URL
                parsed_url = f'https://jx.m3u8.tv/jiexi/?url={content.strip()}'
                # 生成iframe HTML，设置400x400大小
                iframe_html = f"""<iframe class="movie-iframe" src="{parsed_url}" width="400" height="400" frameborder="0" allowfullscreen></iframe>"""
                return {
                    'message': iframe_html,
                    'type': 'movie_link'
                }
            else:
                return {
                    'message': '请提供有效的电影URL地址',
                    'type': 'system'
                }
        # 处理@其他用户
        elif command[1:] in online_users:
            target = command[1:]
            return {
                'message': f'@{target} {content}',
                'type': 'mention'
            }
    
    # 普通消息
    return {
        'message': message,
        'type': 'normal'
    }

@socketio.on('leave')
def handle_leave(data):
    nickname = data['nickname']
    sid = request.sid
    
    if nickname in online_users:
        del online_users[nickname]
        leave_room(room_name, sid)
        emit('user_left', {'nickname': nickname, 'users': list(online_users.keys())}, room=room_name)
        print(f'{nickname} left the chat')

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)