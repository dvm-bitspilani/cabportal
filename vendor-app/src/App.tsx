import { App as CapApp } from '@capacitor/app'
import { IonApp, IonIcon, IonLabel, IonLoading, IonRouterOutlet, IonTabBar, IonTabButton, IonTabs, setupIonicReact } from '@ionic/react'
import { IonReactRouter } from '@ionic/react-router'
import { carSport, construct, people, trailSign } from 'ionicons/icons'
import { useEffect } from 'react'
import { Redirect, Route, useHistory } from 'react-router-dom'
import { useAuth } from './auth'
import Bookings from './pages/Bookings'
import CabBookings from './pages/CabBookings'
import Login from './pages/Login'
import Manage from './pages/Manage'
import Trips from './pages/Trips'
setupIonicReact()
function Protected(){const{vendor,ready}=useAuth();const history=useHistory();useEffect(()=>{let listener:{remove:()=>Promise<void>}|undefined;CapApp.addListener('backButton',({canGoBack})=>canGoBack?history.goBack():CapApp.exitApp()).then(x=>listener=x);return()=>{listener?.remove()}},[history]);if(!ready)return <IonLoading isOpen message="Restoring session…"/>;if(!vendor)return <Login/>;return <IonTabs><IonRouterOutlet><Route exact path="/trips" component={Trips}/><Route exact path="/bookings" component={Bookings}/><Route exact path="/cab-bookings" component={CabBookings}/><Route exact path="/manage" component={Manage}/><Redirect exact from="/" to="/trips"/></IonRouterOutlet><IonTabBar slot="bottom"><IonTabButton tab="trips" href="/trips"><IonIcon icon={trailSign}/><IonLabel>Trips</IonLabel></IonTabButton><IonTabButton tab="bookings" href="/bookings"><IonIcon icon={people}/><IonLabel>Bookings</IonLabel></IonTabButton><IonTabButton tab="cabs" href="/cab-bookings"><IonIcon icon={carSport}/><IonLabel>Cab bookings</IonLabel></IonTabButton><IonTabButton tab="manage" href="/manage"><IonIcon icon={construct}/><IonLabel>Manage</IonLabel></IonTabButton></IonTabBar></IonTabs>}
export default function App(){return <IonApp><IonReactRouter><Protected/></IonReactRouter></IonApp>}
