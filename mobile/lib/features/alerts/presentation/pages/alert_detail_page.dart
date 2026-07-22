import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../../core/models/alert.dart';
import '../../data/alert_repository.dart';
import '../controllers/alert_controller.dart';

/// Alert detail page showing full alert information and actions
/// Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6
class AlertDetailPage extends ConsumerStatefulWidget {
  final String alertId;

  const AlertDetailPage({
    super.key,
    required this.alertId,
  });

  @override
  ConsumerState<AlertDetailPage> createState() => _AlertDetailPageState();
}

class _AlertDetailPageState extends ConsumerState<AlertDetailPage> {
  @override
  void initState() {
    super.initState();
    // Load alert details
    WidgetsBinding.instance.addPostFrameCallback((_) {
      ref.read(alertControllerProvider.notifier).getAlert(widget.alertId);
    });
  }

  @override
  Widget build(BuildContext context) {
    final alertState = ref.watch(alertControllerProvider);
    final selectedAlert = alertState.selectedAlert;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Alert Details'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: () {
              ref.read(alertControllerProvider.notifier).getAlert(widget.alertId);
            },
          ),
        ],
      ),
      body: alertState.isLoading && selectedAlert == null
          ? const Center(child: CircularProgressIndicator())
          : selectedAlert == null
              ? _buildErrorState(alertState.error)
              : _buildAlertDetails(selectedAlert),
    );
  }

  Widget _buildErrorState(String? error) {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(
            Icons.error_outline,
            size: 64,
            color: Colors.grey[400],
          ),
          const SizedBox(height: 16),
          Text(
            error ?? 'Failed to load alert',
            style: Theme.of(context).textTheme.titleMedium?.copyWith(
                  color: Colors.grey[600],
                ),
          ),
        ],
      ),
    );
  }

  Widget _buildAlertDetails(AlertWithVerifications alertWithVerifications) {
    final alert = alertWithVerifications.alert;
    final verifications = alertWithVerifications.verifications;

    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Status card
          _StatusCard(alert: alert),
          const SizedBox(height: 16),

          // Verification progress
          _VerificationProgress(
            current: alert.verificationCount,
            required: alert.requiredVerifications,
            verifications: verifications,
          ),
          const SizedBox(height: 16),

          // Escalation status
          _EscalationStatus(alert: alert),
          const SizedBox(height: 16),

          // Timeline
          _AlertTimeline(alert: alert),
          const SizedBox(height: 24),

          // Actions
          if (alert.status != AlertStatus.resolved) ...[
            _AlertActions(
              alert: alert,
              onEscalate: _escalateAlert,
              onResolve: _resolveAlert,
            ),
          ],
        ],
      ),
    );
  }

  Future<void> _escalateAlert() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Escalate Alert'),
        content: const Text(
          'Are you sure you want to escalate this alert to the next circle level?',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            onPressed: () => Navigator.of(context).pop(true),
            style: ElevatedButton.styleFrom(
              backgroundColor: Colors.orange,
            ),
            child: const Text('Escalate'),
          ),
        ],
      ),
    );

    if (confirmed == true) {
      final success = await ref
          .read(alertControllerProvider.notifier)
          .escalateAlert(widget.alertId);

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              success ? 'Alert escalated successfully' : 'Failed to escalate alert',
            ),
            backgroundColor: success ? Colors.green : Colors.red,
          ),
        );
      }
    }
  }

  Future<void> _resolveAlert() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Resolve Alert'),
        content: const Text(
          'Are you sure you want to resolve this alert? All participants will be notified.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            onPressed: () => Navigator.of(context).pop(true),
            style: ElevatedButton.styleFrom(
              backgroundColor: Colors.green,
            ),
            child: const Text('Resolve'),
          ),
        ],
      ),
    );

    if (confirmed == true) {
      final success = await ref
          .read(alertControllerProvider.notifier)
          .resolveAlert(alertId: widget.alertId);

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              success ? 'Alert resolved successfully' : 'Failed to resolve alert',
            ),
            backgroundColor: success ? Colors.green : Colors.red,
          ),
        );

        if (success) {
          Navigator.of(context).pop();
        }
      }
    }
  }
}


/// Status card widget
class _StatusCard extends StatelessWidget {
  final Alert alert;

  const _StatusCard({required this.alert});

  @override
  Widget build(BuildContext context) {
    final statusColor = _getStatusColor(alert.status);

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Row(
          children: [
            Container(
              width: 48,
              height: 48,
              decoration: BoxDecoration(
                color: statusColor.withOpacity(0.1),
                shape: BoxShape.circle,
              ),
              child: Icon(
                _getAlertIcon(alert.type),
                color: statusColor,
                size: 24,
              ),
            ),
            const SizedBox(width: 16),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    _formatAlertType(alert.type),
                    style: Theme.of(context).textTheme.titleMedium?.copyWith(
                          fontWeight: FontWeight.bold,
                        ),
                  ),
                  const SizedBox(height: 4),
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
                ],
              ),
            ),
          ],
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
        return 'Missing Person Alert';
      case AlertType.emergency:
        return 'Emergency Alert';
      case AlertType.checkIn:
        return 'Check-In Request';
    }
  }
}

/// Verification progress widget
class _VerificationProgress extends StatelessWidget {
  final int current;
  final int required;
  final List<AlertVerification> verifications;

  const _VerificationProgress({
    required this.current,
    required this.required,
    required this.verifications,
  });

  @override
  Widget build(BuildContext context) {
    final isVerified = current >= required;

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(
                  isVerified ? Icons.verified : Icons.pending,
                  color: isVerified ? Colors.green : Colors.orange,
                ),
                const SizedBox(width: 8),
                Text(
                  'Verification Progress',
                  style: Theme.of(context).textTheme.titleSmall?.copyWith(
                        fontWeight: FontWeight.bold,
                      ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            LinearProgressIndicator(
              value: current / required,
              backgroundColor: Colors.grey.shade200,
              color: isVerified ? Colors.green : Colors.orange,
            ),
            const SizedBox(height: 8),
            Text(
              '$current of $required verifications received',
              style: Theme.of(context).textTheme.bodySmall,
            ),
            if (verifications.isNotEmpty) ...[
              const SizedBox(height: 12),
              const Divider(),
              const SizedBox(height: 8),
              ...verifications.map((v) => Padding(
                    padding: const EdgeInsets.symmetric(vertical: 4),
                    child: Row(
                      children: [
                        const Icon(
                          Icons.check_circle,
                          size: 16,
                          color: Colors.green,
                        ),
                        const SizedBox(width: 8),
                        Text(
                          'Verified at ${_formatTime(v.verifiedAt)}',
                          style: Theme.of(context).textTheme.bodySmall,
                        ),
                      ],
                    ),
                  )),
            ],
          ],
        ),
      ),
    );
  }

  String _formatTime(DateTime dateTime) {
    return '${dateTime.hour.toString().padLeft(2, '0')}:${dateTime.minute.toString().padLeft(2, '0')}';
  }
}

/// Escalation status widget
class _EscalationStatus extends StatelessWidget {
  final Alert alert;

  const _EscalationStatus({required this.alert});

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Icon(Icons.trending_up),
                const SizedBox(width: 8),
                Text(
                  'Escalation Level',
                  style: Theme.of(context).textTheme.titleSmall?.copyWith(
                        fontWeight: FontWeight.bold,
                      ),
                ),
              ],
            ),
            const SizedBox(height: 16),
            Row(
              children: [
                _EscalationLevelIndicator(
                  level: 1,
                  label: 'Inner',
                  isActive: alert.escalationLevel >= 1,
                  isCurrent: alert.escalationLevel == 1,
                ),
                Expanded(
                  child: Container(
                    height: 2,
                    color: alert.escalationLevel >= 2
                        ? Colors.blue
                        : Colors.grey.shade300,
                  ),
                ),
                _EscalationLevelIndicator(
                  level: 2,
                  label: 'Community',
                  isActive: alert.escalationLevel >= 2,
                  isCurrent: alert.escalationLevel == 2,
                ),
                Expanded(
                  child: Container(
                    height: 2,
                    color: alert.escalationLevel >= 3
                        ? Colors.blue
                        : Colors.grey.shade300,
                  ),
                ),
                _EscalationLevelIndicator(
                  level: 3,
                  label: 'Professional',
                  isActive: alert.escalationLevel >= 3,
                  isCurrent: alert.escalationLevel == 3,
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

/// Escalation level indicator widget
class _EscalationLevelIndicator extends StatelessWidget {
  final int level;
  final String label;
  final bool isActive;
  final bool isCurrent;

  const _EscalationLevelIndicator({
    required this.level,
    required this.label,
    required this.isActive,
    required this.isCurrent,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Container(
          width: 32,
          height: 32,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            color: isActive ? Colors.blue : Colors.grey.shade300,
            border: isCurrent
                ? Border.all(color: Colors.blue.shade700, width: 3)
                : null,
          ),
          child: Center(
            child: Text(
              '$level',
              style: TextStyle(
                color: isActive ? Colors.white : Colors.grey.shade600,
                fontWeight: FontWeight.bold,
              ),
            ),
          ),
        ),
        const SizedBox(height: 4),
        Text(
          label,
          style: Theme.of(context).textTheme.bodySmall?.copyWith(
                fontWeight: isCurrent ? FontWeight.bold : null,
              ),
        ),
      ],
    );
  }
}

/// Alert timeline widget
class _AlertTimeline extends StatelessWidget {
  final Alert alert;

  const _AlertTimeline({required this.alert});

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Icon(Icons.timeline),
                const SizedBox(width: 8),
                Text(
                  'Timeline',
                  style: Theme.of(context).textTheme.titleSmall?.copyWith(
                        fontWeight: FontWeight.bold,
                      ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            _TimelineItem(
              icon: Icons.add_alert,
              title: 'Alert Created',
              time: alert.createdAt,
              isFirst: true,
            ),
            if (alert.escalatedAt != null)
              _TimelineItem(
                icon: Icons.trending_up,
                title: 'Escalated to Level ${alert.escalationLevel}',
                time: alert.escalatedAt!,
              ),
            if (alert.resolvedAt != null)
              _TimelineItem(
                icon: Icons.check_circle,
                title: 'Alert Resolved',
                time: alert.resolvedAt!,
                isLast: true,
              ),
          ],
        ),
      ),
    );
  }
}

/// Timeline item widget
class _TimelineItem extends StatelessWidget {
  final IconData icon;
  final String title;
  final DateTime time;
  final bool isFirst;
  final bool isLast;

  const _TimelineItem({
    required this.icon,
    required this.title,
    required this.time,
    this.isFirst = false,
    this.isLast = false,
  });

  @override
  Widget build(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Column(
          children: [
            if (!isFirst)
              Container(
                width: 2,
                height: 8,
                color: Colors.grey.shade300,
              ),
            Icon(icon, size: 20),
            if (!isLast)
              Container(
                width: 2,
                height: 24,
                color: Colors.grey.shade300,
              ),
          ],
        ),
        const SizedBox(width: 12),
        Expanded(
          child: Padding(
            padding: const EdgeInsets.only(bottom: 16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                        fontWeight: FontWeight.bold,
                      ),
                ),
                Text(
                  _formatDateTime(time),
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        color: Colors.grey[600],
                      ),
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }

  String _formatDateTime(DateTime dateTime) {
    return '${dateTime.day}/${dateTime.month}/${dateTime.year} at ${dateTime.hour.toString().padLeft(2, '0')}:${dateTime.minute.toString().padLeft(2, '0')}';
  }
}

/// Alert actions widget
class _AlertActions extends StatelessWidget {
  final Alert alert;
  final VoidCallback onEscalate;
  final VoidCallback onResolve;

  const _AlertActions({
    required this.alert,
    required this.onEscalate,
    required this.onResolve,
  });

  @override
  Widget build(BuildContext context) {
    final canEscalate = alert.escalationLevel < 3 &&
        alert.status != AlertStatus.pending;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        if (canEscalate)
          OutlinedButton.icon(
            onPressed: onEscalate,
            icon: const Icon(Icons.trending_up),
            label: const Text('Escalate to Next Level'),
            style: OutlinedButton.styleFrom(
              foregroundColor: Colors.orange,
              side: const BorderSide(color: Colors.orange),
              padding: const EdgeInsets.symmetric(vertical: 12),
            ),
          ),
        if (canEscalate) const SizedBox(height: 12),
        ElevatedButton.icon(
          onPressed: onResolve,
          icon: const Icon(Icons.check_circle),
          label: const Text('Resolve Alert'),
          style: ElevatedButton.styleFrom(
            backgroundColor: Colors.green,
            foregroundColor: Colors.white,
            padding: const EdgeInsets.symmetric(vertical: 12),
          ),
        ),
      ],
    );
  }
}
