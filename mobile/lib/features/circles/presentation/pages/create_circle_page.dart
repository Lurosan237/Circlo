import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../../core/models/circle.dart';
import '../../../../core/services/security_service.dart';
import '../controllers/circle_controller.dart';

/// Page for creating a new circle
class CreateCirclePage extends ConsumerStatefulWidget {
  const CreateCirclePage({super.key});

  @override
  ConsumerState<CreateCirclePage> createState() => _CreateCirclePageState();
}

class _CreateCirclePageState extends ConsumerState<CreateCirclePage> {
  final _formKey = GlobalKey<FormState>();
  final _nameController = TextEditingController();
  
  CircleType _selectedType = CircleType.inner;
  late int _maxMembers;

  @override
  void initState() {
    super.initState();
    _maxMembers = _selectedType.maxMembers;
  }

  @override
  void dispose() {
    _nameController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final circleState = ref.watch(circleControllerProvider);
    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Create Circle'),
      ),
      body: Form(
        key: _formKey,
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            // Circle type selection
            Text(
              'Circle Type',
              style: theme.textTheme.titleMedium,
            ),
            const SizedBox(height: 8),
            _CircleTypeSelector(
              selectedType: _selectedType,
              onTypeSelected: (type) {
                setState(() {
                  _selectedType = type;
                  _maxMembers = type.maxMembers;
                });
              },
            ),
            const SizedBox(height: 24),

            // Circle name
            TextFormField(
              controller: _nameController,
              decoration: const InputDecoration(
                labelText: 'Circle Name',
                hintText: 'Enter a name for your circle',
                prefixIcon: Icon(Icons.group),
              ),
              validator: (value) {
                if (value == null || value.isEmpty) {
                  return 'Please enter a circle name';
                }
                return null;
              },
            ),
            const SizedBox(height: 24),

            // Max members slider
            Text(
              'Maximum Members',
              style: theme.textTheme.titleMedium,
            ),
            const SizedBox(height: 8),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  children: [
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Text(
                          'Min: ${_selectedType.minMembers}',
                          style: theme.textTheme.bodySmall,
                        ),
                        Text(
                          '$_maxMembers members',
                          style: theme.textTheme.titleLarge?.copyWith(
                            color: theme.colorScheme.primary,
                          ),
                        ),
                        Text(
                          'Max: ${_selectedType.maxMembers}',
                          style: theme.textTheme.bodySmall,
                        ),
                      ],
                    ),
                    Slider(
                      value: _maxMembers.toDouble(),
                      min: _selectedType.minMembers.toDouble(),
                      max: _selectedType.maxMembers.toDouble(),
                      divisions: _selectedType.maxMembers - _selectedType.minMembers,
                      label: '$_maxMembers',
                      onChanged: (value) {
                        setState(() {
                          _maxMembers = value.round();
                        });
                      },
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 16),

            // Info card about circle type
            _CircleTypeInfoCard(type: _selectedType),
            const SizedBox(height: 32),

            // Error message
            if (circleState.error != null)
              Padding(
                padding: const EdgeInsets.only(bottom: 16),
                child: Card(
                  color: theme.colorScheme.errorContainer,
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Row(
                      children: [
                        Icon(
                          Icons.error_outline,
                          color: theme.colorScheme.onErrorContainer,
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: Text(
                            circleState.error!,
                            style: TextStyle(
                              color: theme.colorScheme.onErrorContainer,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ),

            // Create button
            FilledButton.icon(
              onPressed: circleState.isLoading ? null : _createCircle,
              icon: circleState.isLoading
                  ? const SizedBox(
                      width: 20,
                      height: 20,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Icon(Icons.add),
              label: Text(circleState.isLoading ? 'Creating...' : 'Create Circle'),
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _createCircle() async {
    if (!_formKey.currentState!.validate()) return;

    // Encrypt the circle name
    final encryptedName = SecurityService.encryptData(_nameController.text);

    final success = await ref.read(circleControllerProvider.notifier).createCircle(
          type: _selectedType,
          nameEncrypted: encryptedName.ciphertext,
          maxMembers: _maxMembers,
        );

    if (success && mounted) {
      Navigator.pop(context);
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Circle created successfully!')),
      );
    }
  }
}

/// Widget for selecting circle type
class _CircleTypeSelector extends StatelessWidget {
  final CircleType selectedType;
  final ValueChanged<CircleType> onTypeSelected;

  const _CircleTypeSelector({
    required this.selectedType,
    required this.onTypeSelected,
  });

  @override
  Widget build(BuildContext context) {
    return Row(
      children: CircleType.values.map((type) {
        final isSelected = type == selectedType;
        return Expanded(
          child: Padding(
            padding: EdgeInsets.only(
              right: type != CircleType.professional ? 8 : 0,
            ),
            child: _CircleTypeCard(
              type: type,
              isSelected: isSelected,
              onTap: () => onTypeSelected(type),
            ),
          ),
        );
      }).toList(),
    );
  }
}

/// Card for a single circle type option
class _CircleTypeCard extends StatelessWidget {
  final CircleType type;
  final bool isSelected;
  final VoidCallback onTap;

  const _CircleTypeCard({
    required this.type,
    required this.isSelected,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Card(
      elevation: isSelected ? 4 : 1,
      color: isSelected
          ? theme.colorScheme.primaryContainer
          : theme.colorScheme.surface,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(12),
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Column(
            children: [
              Icon(
                _getIcon(),
                size: 32,
                color: isSelected
                    ? theme.colorScheme.onPrimaryContainer
                    : _getColor(),
              ),
              const SizedBox(height: 8),
              Text(
                _getShortName(),
                style: theme.textTheme.labelMedium?.copyWith(
                  fontWeight: isSelected ? FontWeight.bold : null,
                  color: isSelected
                      ? theme.colorScheme.onPrimaryContainer
                      : null,
                ),
                textAlign: TextAlign.center,
              ),
            ],
          ),
        ),
      ),
    );
  }

  IconData _getIcon() {
    switch (type) {
      case CircleType.inner:
        return Icons.family_restroom;
      case CircleType.community:
        return Icons.people;
      case CircleType.professional:
        return Icons.local_hospital;
    }
  }

  Color _getColor() {
    switch (type) {
      case CircleType.inner:
        return Colors.red.shade400;
      case CircleType.community:
        return Colors.blue.shade400;
      case CircleType.professional:
        return Colors.green.shade400;
    }
  }

  String _getShortName() {
    switch (type) {
      case CircleType.inner:
        return 'Inner';
      case CircleType.community:
        return 'Community';
      case CircleType.professional:
        return 'Professional';
    }
  }
}

/// Info card showing details about the selected circle type
class _CircleTypeInfoCard extends StatelessWidget {
  final CircleType type;

  const _CircleTypeInfoCard({required this.type});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Card(
      color: theme.colorScheme.surfaceContainerHighest,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(Icons.info_outline, color: theme.colorScheme.primary),
                const SizedBox(width: 8),
                Text(
                  'About ${type.displayName}',
                  style: theme.textTheme.titleSmall,
                ),
              ],
            ),
            const SizedBox(height: 8),
            Text(
              _getDescription(),
              style: theme.textTheme.bodySmall,
            ),
            const SizedBox(height: 8),
            Text(
              'Members: ${type.minMembers}-${type.maxMembers}',
              style: theme.textTheme.bodySmall?.copyWith(
                fontWeight: FontWeight.bold,
              ),
            ),
          ],
        ),
      ),
    );
  }

  String _getDescription() {
    switch (type) {
      case CircleType.inner:
        return 'Your closest family members and friends. They are the first to be notified in an emergency and can verify alerts.';
      case CircleType.community:
        return 'Trusted neighbors and local contacts who can help search in your area. They are notified after Inner Circle escalation.';
      case CircleType.professional:
        return 'Local emergency resources and verified professionals. They are notified for serious situations requiring official assistance.';
    }
  }
}
