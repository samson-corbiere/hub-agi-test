import { DarkTheme, DefaultTheme, ThemeProvider } from 'expo-router';
import { NativeTabs } from 'expo-router/native-tabs';
import { useColorScheme } from 'react-native';

export default function RootLayout() {
  const colorScheme = useColorScheme();
  return (
    <ThemeProvider value={colorScheme === 'dark' ? DarkTheme : DefaultTheme}>
      <NativeTabs>
        <NativeTabs.Trigger name="index">
          <NativeTabs.Trigger.Label>Capture</NativeTabs.Trigger.Label>
          <NativeTabs.Trigger.Icon sf={{ default: 'camera', selected: 'camera.fill' }} />
        </NativeTabs.Trigger>
        <NativeTabs.Trigger name="sessions">
          <NativeTabs.Trigger.Label>Sessions</NativeTabs.Trigger.Label>
          <NativeTabs.Trigger.Icon sf="list.bullet" />
        </NativeTabs.Trigger>
        <NativeTabs.Trigger name="settings">
          <NativeTabs.Trigger.Label>Settings</NativeTabs.Trigger.Label>
          <NativeTabs.Trigger.Icon sf={{ default: 'gearshape', selected: 'gearshape.fill' }} />
        </NativeTabs.Trigger>
      </NativeTabs>
    </ThemeProvider>
  );
}
