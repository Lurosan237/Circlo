import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../../core/models/alert.dart';
import '../controllers/alert_controller.dart';

/// Page for creating a new alert
/// Requirements: 3.1 - Multi-person verification requirement
class CreateAlertPage extends ConsumerStatefulWidget {
  const CreateAlertPage({super.key});

  @override
  ConsumerState<CreateAlertPage> createState() => _CreateAlertPageState();
}

class _CreateAlertPageState extends ConsumerState<CreateAlertPage> {
  AlertType _selectedType = AlertType.missing;
  bool _isCreating = false;

  @override
  Widget build(BuildContext context) {
    final alertState = ref.watch(alertControllerProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Create Alert'),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Warning card
            Card(
              color: Colors.orange.shade50,
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Row(
                  children: [
                    Icon(
                      Icons.info_outline,
                      color: Colors.orange.shade800,
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Text(
                        'Creating an alert will notify your Inner Circle members for verification. 2 out of 3 members must verify before the alert is activated.',
                        style: TextStyle(
                          color: Colors.orange.shade800,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 24),

            // Alert type selection
            Text(
              'Select Alert Type',
              style: Theme.of(context).textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.bold,
                  ),
            ),
            const SizedBox(height: 12),

            _AlertTypeOption(
              type: AlertType.missing,
              title: 'Missing Person',
              description:
                  'Use when someone has gone missing and needs to be located.',
              icon: Icons.person_search,
              isSelected: _selectedType == AlertType.missing,
              onTap: () => setState(() => _selectedType = AlertType.missing),
            ),
            const SizedBox(height: 12),

            _AlertTypeOption(
              type: AlertType.emergency,
              title: 'Emergency',
              description:
                  'Use for immediate emergencies requiring urgent assistance.',
              icon: Icons.emergency,
              isSelected: _selectedType == AlertType.emergency,
              onTap: () => setState(() => _selectedType = AlertType.emergency),
            ),
            const SizedBox(height: 12),

            _AlertTypeOption(
              type: AlertType.checkIn,
              title: 'Check-In Request',
              description:
                  'Request a safety check-in from your circle members.',
              icon: Icons.check_circle,
              isSelected: _selectedType == AlertType.checkIn,
              onTap: () => setState(() => _selectedType = AlertType.checkIn),
            ),

            const SizedBox(height: 32),

            // Escalation info
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Escalation Timeline',
                      style: Theme.of(context).textTheme.titleSmall?.copyWith(
                            fontWeight: FontWeight.bold,
                          ),
                    ),
                    const SizedBox(height: 12),
                    _EscalationStep(
                      step: 1,
                      title: 'Inner Circle',
                      description: 'Immediate notification',
                      isActive: true,
                    ),
                    _EscalationStep(
                      step: 2,
                      title: 'Community Circle',
                      description: 'After 30 minutes if unresolved',
                      isActive: false,
                    ),
                    _EscalationStep(
                      step: 3,
                      title: 'Professional Circle',
                      description: 'After 2 hours if unresolved',
                      isActive: false,
                    ),
                  ],
                ),
              ),
            ),

            const SizedBox(height: 32),

            // Error message
            if (alertState.error != null)
              Container(
                padding: const EdgeInsets.all(12),
                margin: const EdgeInsets.only(bottom: 16),
                decoration: BoxDecoration(
                  color: Colors.red.shade50,
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Row(
                  children: [
                    Icon(Icons.error_outline, color: Colors.red.shade700),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        alertState.error!,
                        style: TextStyle(color: Colors.red.shade700),
                      ),
                    ),
                  ],
                ),
              ),

            // Create button
            SizedBox(
              width: double.infinity,
              child: ElevatedButton(
                onPressed: _isCreating ? null : _createAlert,
                style: ElevatedButton.styleFrom(
                  padding: const EdgeInsets.symmetric(vertical: 16),
                  backgroundColor: Colors.red,
                  foregroundColor: Colors.white,
                ),
                child: _isCreating
                    ? const SizedBox(
                        height: 20,
                        width: 20,
                        child: CircularProgressIndicator(
                          strokeWidth: 2,
                          color: Colors.white,
                        ),
                      )
                    : const Text(
                        'Create Alert',
                        style: TextStyle(
                          fontSize: 16,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _createAlert() async {
    setState(() => _isCreating = true);

    final success = await ref
        .read(alertControllerProvider.notifier)
        .createAlert(type: _selectedType);

    setState(() => _isCreating = false);

    if (success && mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Alert created. Awaiting verification from Inner Circle.'),
          backgroundColor: Colors.green,
        ),
      );
      Navigator.of(context).pop();
    }
  }
}

/// Alert type option widget
class _AlertTypeOption extends StatelessWidget {
  final AlertType type;
  final String title;
  final String description;
  final IconData icon;
  final bool isSelected;
  final VoidCallback onTap;

  const _AlertTypeOption({
    required this.type,
    required this.title,
    required this.description,
    required this.icon,
    required this.isSelected,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(12),
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          border: Border.all(
            color: isSelected
                ? Theme.of(context).colorScheme.primary
                : Colors.grey.shade300,
            width: isSelected ? 2 : 1,
          ),
          borderRadius: BorderRadius.circular(12),
          color: isSelected
              ? Theme.of(context).colorScheme.primary.withOpacity(0.05)
              : null,
        ),
        child: Row(
          children: [
            Icon(
              icon,
              size: 32,
              color: isSelected
                  ? Theme.of(context).colorScheme.primary
                  : Colors.grey,
            ),
            const SizedBox(width: 16),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    title,
                    style: Theme.of(context).textTheme.titleMedium?.copyWith(
                          fontWeight: FontWeight.bold,
                          color: isSelected
                              ? Theme.of(context).colorScheme.primary
                              : null,
                        ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    description,
                    style: Theme.of(context).textTheme.bodySmall?.copyWith(
                          color: Colors.grey[600],
                        ),
                  ),
                ],
              ),
            ),
            if (isSelected)
              Icon(
                Icons.check_circle,
                color: Theme.of(context).colorScheme.primary,
              ),
          ],
        ),
      ),
    );
  }
}

/// Escalation step widget
class _EscalationStep extends StatelessWidget {
  final int step;
  final String title;
  final String description;
  final bool isActive;

  const _EscalationStep({
    required this.step,
    required this.title,
    required this.description,
    required this.isActive,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Row(
        children: [
          Container(
            width: 24,
            height: 24,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: isActive
                  ? Theme.of(context).colorScheme.primary
                  : Colors.grey.shade300,
            ),
            child: Center(
              child: Text(
                '$step',
                style: TextStyle(
                  color: isActive ? Colors.white : Colors.grey.shade600,
                  fontWeight: FontWeight.bold,
                  fontSize: 12,
                ),
              ),
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: TextStyle(
                    fontWeight: FontWeight.bold,
                    color: isActive ? null : Colors.grey.shade600,
                  ),
                ),
                Text(
                  description,
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        color: Colors.grey[600],
                      ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
