import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../../core/models/alert.dart';
import '../../data/alert_repository.dart';
import '../controllers/alert_controller.dart';
import 'create_alert_page.dart';
import 'alert_detail_page.dart';

/// Main alerts page showing user's alerts and pending verifications
/// Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6
class AlertsPage extends ConsumerStatefulWidget {
  const AlertsPage({super.key});

  @override
  ConsumerState<AlertsPage> createState() => _AlertsPageState();
}

class _AlertsPageState extends ConsumerState<AlertsPage>
    with SingleTickerProviderStateMixin {
  late TabController _tabController;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 2, vsync: this);
    
    // Start real-time updates
    WidgetsBinding.instance.addPostFrameCallback((_) {
      ref.read(alertControllerProvider.notifier).startRealTimeUpdates();
    });
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final alertState = ref.watch(alertControllerProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Alerts'),
        bottom: TabBar(
          controller: _tabController,
          tabs: [
            Tab(
              text: 'My Alerts',
              icon: Badge(
                isLabelVisible: alertState.activeAlerts.isNotEmpty,
                label: Text('${alertState.activeAlerts.length}'),
                child: const Icon(Icons.warning_amber),
              ),
            ),
            Tab(
              text: 'Verify',
              icon: Badge(
                isLabelVisible: alertState.pendingVerificationAlerts.isNotEmpty,
                label: Text('${alertState.pendingVerificationAlerts.length}'),
                child: const Icon(Icons.verified_user),
              ),
            ),
          ],
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: () {
              ref.read(alertControllerProvider.notifier).loadAlerts();
            },
          ),
        ],
      ),
      body: TabBarView(
        controller: _tabController,
        children: [
          _buildMyAlertsTab(alertState),
          _buildVerificationTab(alertState),
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: alertState.hasActiveAlert
            ? null
            : () => _navigateToCreateAlert(context),
        icon: const Icon(Icons.add_alert),
        label: const Text('New Alert'),
        backgroundColor:
            alertState.hasActiveAlert ? Colors.grey : null,
      ),
    );
  }

  Widget _buildMyAlertsTab(AlertState alertState) {
    if (alertState.isLoading && alertState.myAlerts.isEmpty) {
      return const Center(child: CircularProgressIndicator());
    }

    if (alertState.myAlerts.isEmpty) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(
              Icons.notifications_off,
              size: 64,
              color: Colors.grey[400],
            ),
            const SizedBox(height: 16),
            Text(
              'No alerts',
              style: Theme.of(context).textTheme.titleLarge?.copyWith(
                    color: Colors.grey[600],
                  ),
            ),
            const SizedBox(height: 8),
            Text(
              'Create an alert if you need help',
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    color: Colors.grey[500],
                  ),
            ),
          ],
        ),
      );
    }

    return RefreshIndicator(
      onRefresh: () => ref.read(alertControllerProvider.notifier).loadAlerts(),
      child: ListView.builder(
        padding: const EdgeInsets.all(16),
        itemCount: alertState.myAlerts.length,
        itemBuilder: (context, index) {
          final alertWithVerifications = alertState.myAlerts[index];
          return _AlertCard(
            alertWithVerifications: alertWithVerifications,
            onTap: () => _navigateToAlertDetail(context, alertWithVerifications),
          );
        },
      ),
    );
  }

  Widget _buildVerificationTab(AlertState alertState) {
    if (alertState.isLoading && alertState.pendingVerificationAlerts.isEmpty) {
      return const Center(child: CircularProgressIndicator());
    }

    if (alertState.pendingVerificationAlerts.isEmpty) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(
              Icons.check_circle_outline,
              size: 64,
              color: Colors.grey[400],
            ),
            const SizedBox(height: 16),
            Text(
              'No pending verifications',
              style: Theme.of(context).textTheme.titleLarge?.copyWith(
                    color: Colors.grey[600],
                  ),
            ),
            const SizedBox(height: 8),
            Text(
              'You\'ll see alerts here when your Inner Circle needs verification',
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    color: Colors.grey[500],
                  ),
              textAlign: TextAlign.center,
            ),
          ],
        ),
      );
    }

    return RefreshIndicator(
      onRefresh: () =>
          ref.read(alertControllerProvider.notifier).loadPendingVerificationAlerts(),
      child: ListView.builder(
        padding: const EdgeInsets.all(16),
        itemCount: alertState.pendingVerificationAlerts.length,
        itemBuilder: (context, index) {
          final alertWithVerifications =
              alertState.pendingVerificationAlerts[index];
          return _VerificationCard(
            alertWithVerifications: alertWithVerifications,
            onVerify: () => _verifyAlert(alertWithVerifications.alert.id),
          );
        },
      ),
    );
  }

  void _navigateToCreateAlert(BuildContext context) {
    Navigator.of(context).push(
      MaterialPageRoute(
        builder: (context) => const CreateAlertPage(),
      ),
    );
  }

  void _navigateToAlertDetail(
      BuildContext context, AlertWithVerifications alert) {
    Navigator.of(context).push(
      MaterialPageRoute(
        builder: (context) => AlertDetailPage(alertId: alert.alert.id),
      ),
    );
  }

  Future<void> _verifyAlert(String alertId) async {
    final success =
        await ref.read(alertControllerProvider.notifier).verifyAlert(alertId);

    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            success ? 'Alert verified successfully' : 'Failed to verify alert',
          ),
          backgroundColor: success ? Colors.green : Colors.red,
        ),
      );
    }
  }
}


/// Alert card widget
class _AlertCard extends StatelessWidget {
  final AlertWithVerifications alertWithVerifications;
  final VoidCallback onTap;

  const _AlertCard({
    required this.alertWithVerifications,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final alert = alertWithVerifications.alert;
    final statusColor = _getStatusColor(alert.status);

    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(12),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 8,
                      vertical: 4,
                    ),
                    decoration: BoxDecoration(
                      color: statusColor.withOpacity(0.1),
                      borderRadius: BorderRadius.circular(4),
                    ),
                    child: Text(
                      alert.status.displayName,
                      style: TextStyle(
                        color: statusColor,
                        fontWeight: FontWeight.bold,
                        fontSize: 12,
                      ),
                    ),
                  ),
                  const Spacer(),
                  Text(
                    _formatAlertType(alert.type),
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                ],
              ),
              const SizedBox(height: 12),
              Row(
                children: [
                  Icon(
                    _getAlertIcon(alert.type),
                    size: 32,
                    color: statusColor,
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'Escalation Level ${alert.escalationLevel}',
                          style: Theme.of(context).textTheme.titleMedium,
                        ),
                        Text(
                          '${alert.verificationCount}/${alert.requiredVerifications} verifications',
                          style: Theme.of(context).textTheme.bodySmall,
                        ),
                      ],
                    ),
                  ),
                  const Icon(Icons.chevron_right),
                ],
              ),
              const SizedBox(height: 8),
              Text(
                'Created ${_formatDateTime(alert.createdAt)}',
                style: Theme.of(context).textTheme.bodySmall?.copyWith(
                      color: Colors.grey[600],
                    ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Color _getStatusColor(AlertStatus status) {
    switch (status) {
      case AlertStatus.pending:
        return Colors.orange;
      case AlertStatus.verified:
        return Colors.blue;
      case AlertStatus.escalated:
        return Colors.red;
      case AlertStatus.resolved:
        return Colors.green;
    }
  }

  IconData _getAlertIcon(AlertType type) {
    switch (type) {
      case AlertType.missing:
        return Icons.person_search;
      case AlertType.emergency:
        return Icons.emergency;
      case AlertType.checkIn:
        return Icons.check_circle;
    }
  }

  String _formatAlertType(AlertType type) {
    switch (type) {
      case AlertType.missing:
        return 'Missing Person';
      case AlertType.emergency:
        return 'Emergency';
      case AlertType.checkIn:
        return 'Check-In';
    }
  }

  String _formatDateTime(DateTime dateTime) {
    final now = DateTime.now();
    final difference = now.difference(dateTime);

    if (difference.inMinutes < 1) {
      return 'just now';
    } else if (difference.inHours < 1) {
      return '${difference.inMinutes}m ago';
    } else if (difference.inDays < 1) {
      return '${difference.inHours}h ago';
    } else {
      return '${difference.inDays}d ago';
    }
  }
}

/// Verification card widget for pending verifications
class _VerificationCard extends StatelessWidget {
  final AlertWithVerifications alertWithVerifications;
  final VoidCallback onVerify;

  const _VerificationCard({
    required this.alertWithVerifications,
    required this.onVerify,
  });

  @override
  Widget build(BuildContext context) {
    final alert = alertWithVerifications.alert;

    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      color: Colors.orange.shade50,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Icon(
                  Icons.warning_amber,
                  color: Colors.orange,
                ),
                const SizedBox(width: 8),
                Text(
                  'Verification Needed',
                  style: Theme.of(context).textTheme.titleMedium?.copyWith(
                        color: Colors.orange.shade800,
                        fontWeight: FontWeight.bold,
                      ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            Text(
              'A member of your Inner Circle needs help. Please verify this alert.',
              style: Theme.of(context).textTheme.bodyMedium,
            ),
            const SizedBox(height: 8),
            Text(
              '${alert.verificationCount}/${alert.requiredVerifications} verifications received',
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    color: Colors.grey[600],
                  ),
            ),
            const SizedBox(height: 16),
            SizedBox(
              width: double.infinity,
              child: ElevatedButton.icon(
                onPressed: onVerify,
                icon: const Icon(Icons.verified_user),
                label: const Text('Verify Alert'),
                style: ElevatedButton.styleFrom(
                  backgroundColor: Colors.orange,
                  foregroundColor: Colors.white,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
