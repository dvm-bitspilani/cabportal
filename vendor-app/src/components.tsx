import { IonButton, IonCard, IonCardContent, IonIcon, IonItem, IonLabel, IonList, IonSkeletonText, IonText } from '@ionic/react'
import { refreshOutline } from 'ionicons/icons'
import type { ReactNode } from 'react'

export function LoadingCards() { return <IonList>{[1,2,3].map(x => <IonCard key={x}><IonCardContent><IonSkeletonText animated style={{ width: '60%' }}/><IonSkeletonText animated/></IonCardContent></IonCard>)}</IonList> }
export function Empty({ title, children }: { title: string; children?: ReactNode }) { return <div className="state"><h2>{title}</h2><IonText color="medium">{children}</IonText></div> }
export function ErrorState({ error, retry }: { error: Error; retry: () => void }) { return <div className="state"><IonText color="danger"><p>{error.message}</p></IonText><IonButton onClick={retry}><IonIcon slot="start" icon={refreshOutline}/>Retry</IonButton></div> }
export function CardList<T>({ items, render }: { items: T[]; render: (item: T) => ReactNode }) { return <IonList lines="none">{items.map(render)}</IonList> }
export const FieldError = ({ message }: { message?: string }) => message ? <IonText color="danger" className="field-error">{message}</IonText> : null
