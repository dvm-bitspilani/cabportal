import React from 'react'
import ReactDOM from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import '@ionic/react/css/core.css'
import '@ionic/react/css/normalize.css'
import '@ionic/react/css/structure.css'
import '@ionic/react/css/typography.css'
import './theme.css'
import App from './App'
import { AuthProvider } from './auth'
const client=new QueryClient({defaultOptions:{queries:{retry:(count,error)=>!(error instanceof Error&&'status'in error&&(error as {status:number}).status>=400)&&count<2,staleTime:30_000},mutations:{retry:false}}})
ReactDOM.createRoot(document.getElementById('root')!).render(<React.StrictMode><QueryClientProvider client={client}><AuthProvider><App/></AuthProvider></QueryClientProvider></React.StrictMode>)
