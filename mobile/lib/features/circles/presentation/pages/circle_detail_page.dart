import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../../core/models/circle.dart';
import '../controllers/circle_controller.dart';

/// Circle detail page showing members and management options
class CircleDetailPage extends ConsumerStatefulWidget {
  final String circleId;

  const CircleDetailPage({
    super.key,
    required this.circleId,
  });

  @override
  ConsumerState<CircleDetailPage> createState() => _CircleDetailPageState();
}

class _CircleDetailPageState extends ConsumerState<CircleDetailPage> {
  @override
  void initState() {
    super.initState();
    // Load circle details
    WidgetsBinding.instance.addPostFrameCallback((_) {
      ref.read(circleControllerProvider.notifier).getCircle(widget.circleId);
    });
  }

  @override
  Widget build(BuildContext context) {
    final circleState = ref.watch(circleControllerProvider);
    final circle = circleState.selectedCircle;
    final theme = Theme.of(context);

    if (circleState.isLoading && circle == null) {
      return Scaffold(
        appBar: AppBar(title: const Text('Circle Details')),
        body: const Center(child: CircularProgressIndicator()),
      );
    }

    if (circle == null) {
      return Scaffold(
        appBar: AppBar(title: const Text('Circle Details')),
        body: Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const Icon(Icons.error_outline, size: 64),
              const SizedBox(height: 16),
              Text(
                circleState.error ?? 'Circle not found',
                style: theme.textTheme.titleMedium,
              ),
              const SizedBox(height: 16),
              FilledButton(
                onPressed: () => Navigator.pop(context),
                child: const Text('Go Back'),
              ),
            ],
          ),
        ),
      );
    }

    final activeMembers =
        circle.members.where((m) => m.status == MemberStatus.active).toList();
    final pendingMembers =
        circle.members.where((m) => m.status == MemberStatus.pending).toList();

    return Scaffold(
      appBar: AppBar(
        title: Text(circle.nameEncrypted), // TODO: Decrypt
        actions: [
          PopupMenuButton<String>(
            onSelected: (value) => _handleMenuAction(value, circle),
            itemBuilder: (context) => [
              const PopupMenuItem(
                value: 'add_member',
                child: ListTile(
                  leading: Icon(Icons.person_add),
                  title: Text('Add Member'),
                  contentPadding: EdgeInsets.zero,
                ),
              ),
              const PopupMenuItem(
                value: 'leave',
                child: ListTile(
                  leading: Icon(Icons.exit_to_app),
                  title: Text('Leave Circle'),
                  contentPadding: EdgeInsets.zero,
                ),
              ),
              const PopupMenuItem(
                value: 'delete',
                child: ListTile(
                  leading: Icon(Icons.delete, color: Colors.red),
                  title: Text('Delete Circle', style: TextStyle(color: Colors.red)),
                  contentPadding: EdgeInsets.zero,
                ),
              ),
            ],
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: () async {
          await ref
              .read(circleControllerProvider.notifier)
              .getCircle(widget.circleId);
        },
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            // Circle info card
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        CircleAvatar(
                          radius: 32,
                          backgroundColor: _getCircleColor(circle.type),
                          child: Icon(
                            _getCircleIcon(circle.type),
                            color: Colors.white,
                            size: 32,
                          ),
                        ),
                        const SizedBox(width: 16),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                circle.type.displayName,
                                style: theme.textTheme.titleLarge,
                              ),
                              const SizedBox(height: 4),
                              Text(
                                '${activeMembers.length}/${circle.maxMembers} active members',
                                style: theme.textTheme.bodyMedium?.copyWith(
                                  color: theme.colorScheme.outline,
                                ),
                              ),
                            ],
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 16),
                    LinearProgressIndicator(
                      value: activeMembers.length / circle.maxMembers,
                      backgroundColor: theme.colorScheme.surfaceContainerHighest,
                    ),
                    const SizedBox(height: 8),
                    Text(
                      'Capacity: ${activeMembers.length}/${circle.maxMembers}',
                      style: theme.textTheme.bodySmall,
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 24),

            // Active members section
            Text(
              'Active Members (${activeMembers.length})',
              style: theme.textTheme.titleMedium,
            ),
            const SizedBox(height: 8),
            if (activeMembers.isEmpty)
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(24),
                  child: Center(
                    child: Text(
                      'No active members yet',
                      style: theme.textTheme.bodyMedium?.copyWith(
                        color: theme.colorScheme.outline,
                      ),
                    ),
                  ),
                ),
              )
            else
              ...activeMembers.map((member) => _MemberCard(
                    member: member,
                    onRemove: () => _removeMember(circle.id, member.userId),
                  )),

            // Pending members section
            if (pendingMembers.isNotEmpty) ...[
              const SizedBox(height: 24),
              Text(
                'Pending Invitations (${pendingMembers.length})',
                style: theme.textTheme.titleMedium,
              ),
              const SizedBox(height: 8),
              ...pendingMembers.map((member) => _MemberCard(
                    member: member,
                    isPending: true,
                    onRemove: () => _removeMember(circle.id, member.userId),
                  )),
            ],
          ],
        ),
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () => _showAddMemberDialog(context, circle),
        icon: const Icon(Icons.person_add),
        label: const Text('Add Member'),
      ),
    );
  }

  void _handleMenuAction(String action, Circle circle) async {
    switch (action) {
      case 'add_member':
        _showAddMemberDialog(context, circle);
        break;
      case 'leave':
        _showLeaveConfirmation(circle);
        break;
      case 'delete':
        _showDeleteConfirmation(circle);
        break;
    }
  }

  void _showAddMemberDialog(BuildContext context, Circle circle) {
    final userIdController = TextEditingController();

    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Add Member'),
        content: TextField(
          controller: userIdController,
          decoration: const InputDecoration(
            labelText: 'User ID',
            hintText: 'Enter the user ID to invite',
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () async {
              if (userIdController.text.isNotEmpty) {
                Navigator.pop(context);
                final success = await ref
                    .read(circleControllerProvider.notifier)
                    .addMember(
                      circleId: circle.id,
                      userId: userIdController.text,
                    );
                if (success && mounted) {
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(content: Text('Invitation sent!')),
                  );
                }
              }
            },
            child: const Text('Invite'),
          ),
        ],
      ),
    );
  }

  void _showLeaveConfirmation(Circle circle) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Leave Circle'),
        content: const Text(
          'Are you sure you want to leave this circle? You will lose access to all circle data.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () async {
              Navigator.pop(context);
              final success = await ref
                  .read(circleControllerProvider.notifier)
                  .leaveCircle(circle.id);
              if (success && mounted) {
                Navigator.pop(context);
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(content: Text('Left circle successfully')),
                );
              }
            },
            style: FilledButton.styleFrom(
              backgroundColor: Colors.orange,
            ),
            child: const Text('Leave'),
          ),
        ],
      ),
    );
  }

  void _showDeleteConfirmation(Circle circle) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Delete Circle'),
        content: const Text(
          'Are you sure you want to delete this circle? This action cannot be undone and all members will lose access.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () async {
              Navigator.pop(context);
              final success = await ref
                  .read(circleControllerProvider.notifier)
                  .deleteCircle(circle.id);
              if (success && mounted) {
                Navigator.pop(context);
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(content: Text('Circle deleted')),
                );
              }
            },
            style: FilledButton.styleFrom(
              backgroundColor: Colors.red,
            ),
            child: const Text('Delete'),
          ),
        ],
      ),
    );
  }

  Future<void> _removeMember(String circleId, String userId) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Remove Member'),
        content: const Text(
          'Are you sure you want to remove this member? They will immediately lose access to the circle.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            style: FilledButton.styleFrom(backgroundColor: Colors.red),
            child: const Text('Remove'),
          ),
        ],
      ),
    );

    if (confirmed == true) {
      final success = await ref
          .read(circleControllerProvider.notifier)
          .removeMember(circleId: circleId, userId: userId);
      if (success && mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Member removed')),
        );
      }
    }
  }

  Color _getCircleColor(CircleType type) {
    switch (type) {
      case CircleType.inner:
        return Colors.red.shade400;
      case CircleType.community:
        return Colors.blue.shade400;
      case CircleType.professional:
        return Colors.green.shade400;
    }
  }

  IconData _getCircleIcon(CircleType type) {
    switch (type) {
      case CircleType.inner:
        return Icons.family_restroom;
      case CircleType.community:
        return Icons.people;
      case CircleType.professional:
        return Icons.local_hospital;
    }
  }
}

/// Card widget for displaying a circle member
class _MemberCard extends StatelessWidget {
  final CircleMember member;
  final bool isPending;
  final VoidCallback onRemove;

  const _MemberCard({
    required this.member,
    this.isPending = false,
    required this.onRemove,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      child: ListTile(
        leading: CircleAvatar(
          backgroundColor: isPending
              ? theme.colorScheme.surfaceContainerHighest
              : theme.colorScheme.primaryContainer,
          child: Icon(
            Icons.person,
            color: isPending
                ? theme.colorScheme.outline
                : theme.colorScheme.onPrimaryContainer,
          ),
        ),
        title: Text(member.userId), // TODO: Show user name
        subtitle: Text(
          isPending
              ? 'Pending verification'
              : 'Joined ${_formatDate(member.verifiedAt)}',
          style: TextStyle(
            color: isPending ? Colors.orange : null,
          ),
        ),
        trailing: IconButton(
          icon: const Icon(Icons.remove_circle_outline),
          color: Colors.red,
          onPressed: onRemove,
          tooltip: 'Remove member',
        ),
      ),
    );
  }

  String _formatDate(DateTime? date) {
    if (date == null) return 'Unknown';
    return '${date.day}/${date.month}/${date.year}';
  }
}
