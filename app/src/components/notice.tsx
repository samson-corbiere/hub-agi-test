import { Pressable, StyleSheet, Text, View, useColorScheme } from 'react-native';

type Props = {
  title: string;
  message: string;
  action?: { label: string; onPress: () => void };
};

/** Centered title, explanation and optional button, used for empty and blocked states. */
export function Notice({ title, message, action }: Props) {
  const dark = useColorScheme() === 'dark';
  const textColor = dark ? '#FFFFFF' : '#000000';
  return (
    <View style={styles.container}>
      <Text style={[styles.title, { color: textColor }]}>{title}</Text>
      <Text style={[styles.message, { color: textColor }]}>{message}</Text>
      {action && (
        <Pressable
          accessibilityRole="button"
          onPress={action.onPress}
          style={({ pressed }) => [styles.button, pressed && styles.buttonPressed]}>
          <Text style={styles.buttonLabel}>{action.label}</Text>
        </Pressable>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 32,
    gap: 12,
  },
  title: { fontSize: 22, fontWeight: '600', textAlign: 'center' },
  message: { fontSize: 16, textAlign: 'center', opacity: 0.7 },
  button: {
    marginTop: 8,
    paddingHorizontal: 20,
    paddingVertical: 12,
    borderRadius: 12,
    backgroundColor: '#007AFF',
  },
  buttonPressed: { opacity: 0.7 },
  buttonLabel: { color: '#FFFFFF', fontSize: 16, fontWeight: '600' },
});
