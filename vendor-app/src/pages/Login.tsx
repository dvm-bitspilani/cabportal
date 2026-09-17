import { zodResolver } from '@hookform/resolvers/zod'
import { IonButton, IonContent, IonInput, IonPage, IonText } from '@ionic/react'
import { useState } from 'react'
import { Controller, useForm } from 'react-hook-form'
import { z } from 'zod'
import { useAuth } from '../auth'
import { FieldError } from '../components'

const schema = z.object({ username: z.string().min(1, 'Username is required'), password: z.string().min(1, 'Password is required') })
type Form = z.infer<typeof schema>
export default function Login() {
  const { login } = useAuth(); const [error, setError] = useState(''); const { control, handleSubmit, formState: { errors, isSubmitting } } = useForm<Form>({ resolver: zodResolver(schema), defaultValues: { username: '', password: '' } })
  return <IonPage><IonContent className="login"><div className="login-card"><div className="brand-mark">R</div><h1>Ridezy Vendor</h1><p>Run every ride from one place.</p><form onSubmit={handleSubmit(async v => { setError(''); try { await login(v.username, v.password) } catch (e) { setError((e as Error).message) } })}>
    <Controller name="username" control={control} render={({ field }) => <IonInput label="Username" labelPlacement="stacked" fill="outline" value={field.value} onIonInput={e => field.onChange(e.detail.value!)} />}/><FieldError message={errors.username?.message}/>
    <Controller name="password" control={control} render={({ field }) => <IonInput label="Password" labelPlacement="stacked" fill="outline" type="password" value={field.value} onIonInput={e => field.onChange(e.detail.value!)} />}/><FieldError message={errors.password?.message}/>
    {error && <IonText color="danger"><p>{error}</p></IonText>}<IonButton expand="block" type="submit" disabled={isSubmitting}>{isSubmitting ? 'Signing in…' : 'Sign in'}</IonButton>
  </form></div></IonContent></IonPage>
}
