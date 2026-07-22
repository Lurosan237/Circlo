import 'package:flutter/material.dart';
import '../../../../core/services/realtime_service.dart';

/// Widget for displaying a single chat message
class ChatMessageWidget extends StatelessWidget {
  final ChatMessage message;
  final bool isCurrentUser;

  const ChatMessageWidget({
    super.key,
    required this.message,
    required this.isCurrentUser,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
      child: Row(
        mainAxisAlignment:
            isCurrentUser ? MainAxisAlignment.end : MainAxisAlignment.start,
        children: [
          Container(
            constraints: BoxConstraints(
              maxWidth: MediaQuery.of(context).size.width * 0.75,
            ),
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
            decoration: BoxDecoration(
              color: isCurrentUser
                  ? theme.colorScheme.primary
                  : theme.colorScheme.surfaceContainerHighest,
              borderRadius: BorderRadius.circular(20),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  message.content,
                  style: TextStyle(
                    color: isCurrentUser
                        ? theme.colorScheme.onPrimary
                        : theme.colorScheme.onSurface,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  _formatTime(message.sentAt),
                  style: TextStyle(
                    fontSize: 10,
                    color: isCurrentUser
                        ? theme.colorScheme.onPrimary.withOpacity(0.7)
                        : theme.colorScheme.onSurface.withOpacity(0.5),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  String _formatTime(DateTime time) {
    final hour = time.hour.toString().padLeft(2, '0');
    final minute = time.minute.toString().padLeft(2, '0');
    return '$hour:$minute';
  }
}

/// Widget for the chat input field
class ChatInputWidget extends StatefulWidget {
  final Function(String) onSend;
  final bool enabled;

  const ChatInputWidget({
    super.key,
    required this.onSend,
    this.enabled = true,
  });

  @override
  State<ChatInputWidget> createState() => _ChatInputWidgetState();
}

class _ChatInputWidgetState extends State<ChatInputWidget> {
  final _controller = TextEditingController();
  bool _hasText = false;

  @override
  void initState() {
    super.initState();
    _controller.addListener(() {
      setState(() {
        _hasText = _controller.text.trim().isNotEmpty;
      });
    });
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  void _handleSend() {
    final text = _controller.text.trim();
    if (text.isNotEmpty && widget.enabled) {
      widget.onSend(text);
      _controller.clear();
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Container(
      padding: const EdgeInsets.all(8),
      decoration: BoxDecoration(
        color: theme.colorScheme.surface,
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.1),
            blurRadius: 4,
            offset: const Offset(0, -2),
          ),
        ],
      ),
      child: SafeArea(
        child: Row(
          children: [
            Expanded(
              child: TextField(
                controller: _controller,
                enabled: widget.enabled,
                decoration: InputDecoration(
                  hintText: 'Type a message...',
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(24),
                    borderSide: BorderSide.none,
                  ),
                  filled: true,
                  fillColor: theme.colorScheme.surfaceContainerHighest,
                  contentPadding: const EdgeInsets.symmetric(
                    horizontal: 16,
                    vertical: 8,
                  ),
                ),
                textInputAction: TextInputAction.send,
                onSubmitted: (_) => _handleSend(),
              ),
            ),
            const SizedBox(width: 8),
            IconButton.filled(
              onPressed: _hasText && widget.enabled ? _handleSend : null,
              icon: const Icon(Icons.send),
            ),
          ],
        ),
      ),
    );
  }
}

/// Widget showing connection status
class ConnectionStatusWidget extends StatelessWidget {
  final ConnectionState connectionState;

  const ConnectionStatusWidget({
    super.key,
    required this.connectionState,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    
    Color color;
    String text;
    IconData icon;

    switch (connectionState) {
      case ConnectionState.connected:
        color = Colors.green;
        text = 'Connected';
        icon = Icons.wifi;
        break;
      case ConnectionState.connecting:
        color = Colors.orange;
        text = 'Connecting...';
        icon = Icons.wifi_find;
        break;
      case ConnectionState.reconnecting:
        color = Colors.orange;
        text = 'Reconnecting...';
        icon = Icons.wifi_find;
        break;
      case ConnectionState.disconnected:
        color = Colors.grey;
        text = 'Disconnected';
        icon = Icons.wifi_off;
        break;
      case ConnectionState.error:
        color = Colors.red;
        text = 'Connection Error';
        icon = Icons.error_outline;
        break;
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      decoration: BoxDecoration(
        color: color.withOpacity(0.1),
        borderRadius: BorderRadius.circular(16),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 16, color: color),
          const SizedBox(width: 4),
          Text(
            text,
            style: TextStyle(
              fontSize: 12,
              color: color,
              fontWeight: FontWeight.w500,
            ),
          ),
        ],
      ),
    );
  }
}
