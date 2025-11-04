// profile.js

let registeredDevices = JSON.parse(localStorage.getItem('registeredDevices') || '[]');

function registerUser(email, password) {
  const users = JSON.parse(localStorage.getItem('users') || '[]');
  if (users.some(u => u.email === email)) return false;
  users.push({ email, password });
  localStorage.setItem('users', JSON.stringify(users));
  return true;
}

function loginUser(email, password) {
  const users = JSON.parse(localStorage.getItem('users') || '[]');
  const user = users.find(u => u.email === email && u.password === password);
  if (user) {
    localStorage.setItem('currentUser', email);
    return true;
  }
  return false;
}

function isUserLoggedIn() {
  return localStorage.getItem('currentUser') !== null;
}

function getUserDevices() {
  const email = localStorage.getItem('currentUser');
  return registeredDevices.filter(d => d.owner === email);
}

function addDeviceToAccount(code, name) {
  const email = localStorage.getItem('currentUser');
  if (registeredDevices.some(d => d.code === code)) {
    return false; // уже занято
  }
  registeredDevices.push({ code, name, owner: email });
  localStorage.setItem('registeredDevices', JSON.stringify(registeredDevices));
  return true;
}