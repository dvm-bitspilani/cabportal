import { DateTime } from 'luxon'
export const APP_ZONE = 'Asia/Kolkata'
export const displayDateTime = (iso: string) => DateTime.fromISO(iso).setZone(APP_ZONE).toFormat('dd LLL yyyy, hh:mm a')
export const isoToLocalInput = (iso: string) => DateTime.fromISO(iso).setZone(APP_ZONE).toFormat("yyyy-LL-dd'T'HH:mm")
export const localInputToIso = (value: string) => DateTime.fromISO(value, { zone: APP_ZONE }).toUTC().toISO()
