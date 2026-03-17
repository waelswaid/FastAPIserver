import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'

export default function Home() {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()

  useEffect(() => {
    const token = localStorage.getItem('access_token')
    if (!token) {
      navigate('/login')
      return
    }

    fetch('/api/users/me', {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((res) => {
        if (!res.ok) {
          localStorage.removeItem('access_token')
          navigate('/login')
          return null
        }
        return res.json()
      })
      .then((data) => {
        if (data) setUser(data)
      })
      .finally(() => setLoading(false))
  }, [navigate])

  function handleLogout() {
    const token = localStorage.getItem('access_token')
    fetch('/api/auth/logout', {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` },
    }).finally(() => {
      localStorage.removeItem('access_token')
      navigate('/login')
    })
  }

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <p className="text-gray-500">Loading...</p>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white shadow-sm">
        <div className="max-w-3xl mx-auto px-4 py-4 flex items-center justify-between">
          <h1 className="text-lg font-bold text-gray-900">Dashboard</h1>
          <button
            onClick={handleLogout}
            className="text-sm text-red-600 hover:text-red-700 font-medium"
          >
            Sign out
          </button>
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-4 py-8">
        <div className="bg-white rounded-2xl shadow-lg p-8">
          <h2 className="text-xl font-bold text-gray-900 mb-6">Your Profile</h2>

          <div className="space-y-4">
            <div>
              <p className="text-sm text-gray-500">Name</p>
              <p className="text-gray-900 font-medium">{user.name}</p>
            </div>
            <div>
              <p className="text-sm text-gray-500">Email</p>
              <p className="text-gray-900 font-medium">{user.email}</p>
            </div>
            <div>
              <p className="text-sm text-gray-500">User ID</p>
              <p className="text-gray-900 font-mono text-sm">{user.id}</p>
            </div>
            <div>
              <p className="text-sm text-gray-500">Account created</p>
              <p className="text-gray-900 font-medium">
                {new Date(user.created_at).toLocaleDateString('en-US', {
                  year: 'numeric',
                  month: 'long',
                  day: 'numeric',
                })}
              </p>
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}
