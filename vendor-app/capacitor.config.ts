import type { CapacitorConfig } from '@capacitor/cli'

const config: CapacitorConfig = {
  appId: 'com.ridezy.vendor',
  appName: 'Ridezy Vendor',
  webDir: 'dist',
  server: { androidScheme: 'https', allowNavigation: ['cab.bits-oasis.org'] },
  plugins: {
    StatusBar: { style: 'DARK', backgroundColor: '#fffaf4' },
    Keyboard: { resize: 'body', resizeOnFullScreen: true },
    SplashScreen: { launchShowDuration: 1500, backgroundColor: '#fffaf4', showSpinner: false }
  }
}
export default config
