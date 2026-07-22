import 'package:flutter/material.dart';
import '../../../../core/theme/app_theme.dart';

/// Home page displaying safety circles and alert options
class HomePage extends StatelessWidget {
  const HomePage({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Circlo Safety'),
        actions: [
          IconButton(
            icon: const Icon(Icons.notifications_outlined),
            onPressed: () {
              // TODO: Navigate to notifications
            },
          ),
          IconButton(
            icon: const Icon(Icons.settings_outlined),
            onPressed: () {
              // TODO: Navigate to settings
            },
          ),
        ],
      ),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(16.0),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Safety status card
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(20.0),
                  child: Column(
                    children: [
                      const Icon(
                        Icons.check_circle,
                        size: 48,
                        color: Colors.green,
                      ),
                      const SizedBox(height: 12),
                      const Text(
                        'You are safe',
                        style: TextStyle(
                          fontSize: 20,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        'All circles are active',
                        style: TextStyle(
                          color: Colors.grey[600],
                        ),
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 24),
              // Safety circles section
              const Text(
                'Your Safety Circles',
                style: TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.bold,
                ),
              ),
              const SizedBox(height: 12),
              // Inner Circle
              _buildCircleCard(
                context,
                title: 'Inner Circle',
                subtitle: '0/5 members',
                color: AppTheme.innerCircleColor,
                icon: Icons.favorite,
              ),
              const SizedBox(height: 8),
              // Community Circle
              _buildCircleCard(
                context,
                title: 'Community Circle',
                subtitle: '0/30 members',
                color: AppTheme.communityCircleColor,
                icon: Icons.people,
              ),
              const SizedBox(height: 8),
              // Professional Circle
              _buildCircleCard(
                context,
                title: 'Professional Circle',
                subtitle: '0 resources',
                color: AppTheme.professionalCircleColor,
                icon: Icons.local_hospital,
              ),
              const SizedBox(height: 24),
              // Emergency button
              SizedBox(
                width: double.infinity,
                child: ElevatedButton.icon(
                  onPressed: () {
                    // TODO: Implement alert trigger
                    _showAlertDialog(context);
                  },
                  icon: const Icon(Icons.warning_amber),
                  label: const Padding(
                    padding: EdgeInsets.all(12.0),
                    child: Text('Trigger Alert'),
                  ),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: Colors.red,
                    foregroundColor: Colors.white,
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildCircleCard(
    BuildContext context, {
    required String title,
    required String subtitle,
    required Color color,
    required IconData icon,
  }) {
    return Card(
      child: ListTile(
        leading: CircleAvatar(
          backgroundColor: color.withOpacity(0.2),
          child: Icon(icon, color: color),
        ),
        title: Text(title),
        subtitle: Text(subtitle),
        trailing: const Icon(Icons.chevron_right),
        onTap: () {
          // TODO: Navigate to circle management
        },
      ),
    );
  }

  void _showAlertDialog(BuildContext context) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Trigger Alert?'),
        content: const Text(
          'This will notify your Inner Circle members for verification. '
          'Are you sure you want to proceed?',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            onPressed: () {
              Navigator.pop(context);
              // TODO: Implement alert trigger
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(
                  content: Text('Alert sent to Inner Circle for verification'),
                ),
              );
            },
            style: ElevatedButton.styleFrom(
              backgroundColor: Colors.red,
              foregroundColor: Colors.white,
            ),
            child: const Text('Trigger Alert'),
          ),
        ],
      ),
    );
  }
}
