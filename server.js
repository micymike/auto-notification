const express = require('express');
const http = require('http');
const socketIo = require('socket.io');

const app = express();
const server = http.createServer(app);
const io = socketIo(server);

io.on('connection', (socket) => {
    console.log('a user connected');
    socket.on('disconnect', () => {
        console.log('user disconnected');
    });
});

// Listen for messages from Flask app
io.on('new_message', (data) => {
    io.emit('new_message', data);
});

server.listen(3000, () => {
    console.log('listening on *:3000');
});
