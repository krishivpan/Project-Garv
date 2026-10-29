

const socket = new WebSocket('ws://localhost:8000/ws');
socket.onmessage = (event) => {
  console.log(JSON.parse(event.data));
}

function App() {
  return <>

  
  </>
}

