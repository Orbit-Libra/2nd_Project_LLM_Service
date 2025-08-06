//인증 관련 JavaScript
let currentUser = null;

// 로그인 상태 확인
function checkLoginStatus() {
    const savedUser = localStorage.getItem('libra_user');
    if (savedUser) {
        currentUser = JSON.parse(savedUser);
        updateHeaderForLoggedUser();
    }
}

// 헤더를 로그인된 사용자용으로 업데이트
function updateHeaderForLoggedUser() {
    const loginBtn = document.querySelector('.login-btn');
    if (loginBtn && currentUser) {
        loginBtn.innerHTML = `
            <span class="login-icon">👤</span>
            My Page
        `;
        loginBtn.onclick = () => navigateTo('mypage');
        
        // 마이서비스 메뉴 추가
        const navMenu = document.querySelector('.nav-menu');
        if (navMenu && !document.getElementById('myserviceNav')) {
            const myServiceItem = document.createElement('a');
            myServiceItem.href = '#';
            myServiceItem.className = 'nav-item';
            myServiceItem.id = 'myserviceNav';
            myServiceItem.textContent = '마이 서비스';
            myServiceItem.onclick = () => navigateTo('myservice');
            navMenu.appendChild(myServiceItem);
        }
    }
}

// 로그인 모달 열기
function openAuthModal() {
    if (currentUser) {
        navigateTo('mypage');
    } else {
        document.getElementById('authModal').style.display = 'block';
    }
}

// 로그인 모달 닫기
function closeAuthModal() {
    document.getElementById('authModal').style.display = 'none';
}

// 로그인/회원가입 폼 전환
function switchToRegister() {
    document.getElementById('loginForm').style.display = 'none';
    document.getElementById('registerForm').style.display = 'block';
}

function switchToLogin() {
    document.getElementById('loginForm').style.display = 'block';
    document.getElementById('registerForm').style.display = 'none';
}

// 로그인 처리
async function handleLogin(event) {
    event.preventDefault();
    const formData = new FormData(event.target);
    const loginData = {
        userId: formData.get('loginId'),
        password: formData.get('loginPassword')
    };
    
    try {
        // Flask 백엔드로 로그인 요청
        const response = await fetch('/api/login', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(loginData)
        });
        
        const result = await response.json();
        
        if (result.success) {
            currentUser = result.user;
            localStorage.setItem('libra_user', JSON.stringify(currentUser));
            updateHeaderForLoggedUser();
            closeAuthModal();
            alert('로그인 성공!');
        } else {
            alert('로그인 실패: ' + result.message);
        }
    } catch (error) {
        console.error('로그인 오류:', error);
        alert('로그인 중 오류가 발생했습니다.');
    }
}

// 회원가입 처리
async function handleRegister(event) {
    event.preventDefault();
    const formData = new FormData(event.target);
    
    // 유효성 검사
    if (!validateRegistration(formData)) {
        return;
    }
    
    const registerData = {
        name: formData.get('name'),
        phone: formData.get('phone'),
        userId: formData.get('userId'),
        password: formData.get('password'),
        email: formData.get('email')
    };
    
    try {
        // Flask 백엔드로 회원가입 요청
        const response = await fetch('/api/register', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(registerData)
        });
        
        const result = await response.json();
        
        if (result.success) {
            alert('회원가입이 완료되었습니다!');
            switchToLogin();
        } else {
            alert('회원가입 실패: ' + result.message);
        }
    } catch (error) {
        console.error('회원가입 오류:', error);
        alert('회원가입 중 오류가 발생했습니다.');
    }
}

// 회원가입 유효성 검사
function validateRegistration(formData) {
    const name = formData.get('name');
    const phone = formData.get('phone');
    const userId = formData.get('userId');
    const password = formData.get('password');
    const email = formData.get('email');
    
    if (name.length < 2) {
        alert('이름은 2자 이상이어야 합니다.');
        return false;
    }
    
    const phonePattern = /^[0-9]{10,11}$/;
    if (!phonePattern.test(phone.replace(/-/g, ''))) {
        alert('올바른 전화번호를 입력해주세요.');
        return false;
    }
    
    if (userId.length < 4) {
        alert('아이디는 4자 이상이어야 합니다.');
        return false;
    }
    
    if (password.length < 6) {
        alert('비밀번호는 6자 이상이어야 합니다.');
        return false;
    }
    
    const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailPattern.test(email)) {
        alert('올바른 이메일 주소를 입력해주세요.');
        return false;
    }
    
    return true;
}

// 로그아웃
function logout() {
    currentUser = null;
    localStorage.removeItem('libra_user');
    location.reload();
}

// 페이지 로드시 로그인 상태 확인
window.addEventListener('load', checkLoginStatus);