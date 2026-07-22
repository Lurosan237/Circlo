import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../../core/models/circle.dart';
import '../controllers/circle_controller.dart';
import '../../data/circle_repository.dart';

/// Main circles page showing all user's circles
class CirclesPage extends ConsumerStatefulWidget {
  const CirclesPage({super.key});

  @override
  ConsumerState<CirclesPage> createState() => _CirclesPageState();
}

class _CirclesPageState extends ConsumerState<CirclesPage>
    with SingleTickerProviderStateMixin {
  late TabController _tabController;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 4, vsync: this);
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final circleState = ref.watch(circleControllerProvider);
    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Safety Circles'),
        bottom: TabBar(
          controller: _tabController,
          isScrollable: true,
          tabs: [
            Tab(
              text: 'All',
              icon: Badge(
                label: Text('${circleState.circles.length}'),
                isLabelVisible: circleState.circles.isNotEmpty,
                child: const Icon(Icons.groups),
              ),
            ),
            Tab(
              text: 'Inner',
              icon: Badge(
                label: Text('${circleState.innerCircles.length}'),
                isLabelVisible: circleState.innerCircles.isNotEmpty,
                child: const Icon(Icons.family_restroom),
              ),
            ),
            Tab(
              text: 'Community',
              icon: Badge(
                label: Text('${circleState.communityCircles.length}'),
                isLabelVisible: circleState.communityCircles.isNotEmpty,
                child: const Icon(Icons.people),
              ),
            ),
            Tab(
              text: 'Professional',
              icon: Badge(
                label: Text('${circleState.professionalCircles.length}'),
                isLabelVisible: circleState.professionalCircles.isNotEmpty,
                child: const Icon(Icons.local_hospital),
              ),
            ),
          ],
        ),
        actions: [
          if (circleState.pendingInvitations.isNotEmpty)
            Badge(
              label: Text('${circleState.pendingInvitations.length}'),
              child: IconButton(
                icon: const Icon(Icons.mail),
                onPressed: () => _showInvitations(context),
                tooltip: 'Pending Invitations',
              ),
            ),
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: () {
              ref.read(circleControllerProvider.notifier).loadCircles();
            },
            tooltip: 'Refresh',
          ),
        ],
      ),
      body: circleState.isLoading
          ? const Center(child: CircularProgressIndicator())
          : TabBarView(
              controller: _tabController,
              children: [
                _buildCircleList(circleState.circles),
                _buildCircleList(circleState.innerCircles),
                _buildCircleList(circleState.communityCircles),
                _buildCircleList(circleState.professionalCircles),
              ],
            ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () => Navigator.pushNamed(context, '/circles/create'),
        icon: const Icon(Icons.add),
        label: const Text('Create Circle'),
      ),
    );
  }

  Widget _buildCircleList(List<Circle> circles) {
    if (circles.isEmpty) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(
              Icons.group_off,
              size: 64,
              color: Theme.of(context).colorScheme.outline,
            ),
            const SizedBox(height: 16),
            Text(
              'No circles yet',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 8),
            Text(
              'Create a circle to start building your safety network',
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    color: Theme.of(context).colorScheme.outline,
                  ),
              textAlign: TextAlign.center,
            ),
          ],
        ),
      );
    }

    return RefreshIndicator(
      onRefresh: () async {
        await ref.read(circleControllerProvider.notifier).loadCircles();
      },
      child: ListView.builder(
        padding: const EdgeInsets.all(16),
        itemCount: circles.length,
        itemBuilder: (context, index) {
          final circle = circles[index];
          return _CircleCard(
            circle: circle,
            onTap: () {
              ref.read(circleControllerProvider.notifier).selectCircle(circle);
              Navigator.pushNamed(
                context,
                '/circles/detail',
                arguments: circle.id,
              );
            },
          );
        },
      ),
    );
  }

  void _showInvitations(BuildContext context) {
    final invitations = ref.read(circleControllerProvider).pendingInvitations;

    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      builder: (context) => DraggableScrollableSheet(
        initialChildSize: 0.5,
        minChildSize: 0.3,
        maxChildSize: 0.9,
        expand: false,
        builder: (context, scrollController) => Column(
          children: [
            Padding(
              padding: const EdgeInsets.all(16),
              child: Row(
                children: [
                  const Icon(Icons.mail),
                  const SizedBox(width: 8),
                  Text(
                    'Pending Invitations',
                    style: Theme.of(context).textTheme.titleLarge,
                  ),
                ],
              ),
            ),
            const Divider(),
            Expanded(
              child: ListView.builder(
                controller: scrollController,
                itemCount: invitations.length,
                itemBuilder: (context, index) {
                  final invitation = invitations[index];
                  return _InvitationCard(
                    invitation: invitation,
                    onAccept: () async {
                      final success = await ref
                          .read(circleControllerProvider.notifier)
                          .verifyMembership(invitation.circleId);
                      if (success && context.mounted) {
                        Navigator.pop(context);
                        ScaffoldMessenger.of(context).showSnackBar(
                          const SnackBar(
                            content: Text('Invitation accepted!'),
                          ),
                        );
                      }
                    },
                  );
                },
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// Card widget for displaying a circle
class _CircleCard extends StatelessWidget {
  final Circle circle;
  final VoidCallback onTap;

  const _CircleCard({
    required this.circle,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(12),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Row(
            children: [
              CircleAvatar(
                backgroundColor: _getCircleColor(circle.type),
                child: Icon(
                  _getCircleIcon(circle.type),
                  color: Colors.white,
                ),
              ),
              const SizedBox(width: 16),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      circle.nameEncrypted, // TODO: Decrypt name
                      style: theme.textTheme.titleMedium,
                    ),
                    const SizedBox(height: 4),
                    Text(
                      '${circle.type.displayName} • ${circle.members.where((m) => m.status == MemberStatus.active).length}/${circle.maxMembers} members',
                      style: theme.textTheme.bodySmall?.copyWith(
                        color: theme.colorScheme.outline,
                      ),
                    ),
                  ],
                ),
              ),
              const Icon(Icons.chevron_right),
            ],
          ),
        ),
      ),
    );
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

/// Card widget for displaying a pending invitation
class _InvitationCard extends StatelessWidget {
  final PendingInvitation invitation;
  final VoidCallback onAccept;

  const _InvitationCard({
    required this.invitation,
    required this.onAccept,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Card(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                CircleAvatar(
                  backgroundColor: _getCircleColor(invitation.circleType),
                  child: Icon(
                    _getCircleIcon(invitation.circleType),
                    color: Colors.white,
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        invitation.circleNameEncrypted, // TODO: Decrypt
                        style: theme.textTheme.titleMedium,
                      ),
                      Text(
                        invitation.circleType.displayName,
                        style: theme.textTheme.bodySmall?.copyWith(
                          color: theme.colorScheme.outline,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            Row(
              mainAxisAlignment: MainAxisAlignment.end,
              children: [
                TextButton(
                  onPressed: () => Navigator.pop(context),
                  child: const Text('Decline'),
                ),
                const SizedBox(width: 8),
                FilledButton(
                  onPressed: onAccept,
                  child: const Text('Accept'),
                ),
              ],
            ),
          ],
        ),
      ),
    );
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
