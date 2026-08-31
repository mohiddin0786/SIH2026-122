import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { AppLayout } from '../components/layout/AppLayout';
import Dashboard from '../pages/Dashboard';
import Reports from '../pages/Reports';
import Activities from '../pages/Activities';
import ActivityDetail from '../pages/ActivityDetail';
import Attention from '../pages/Attention';

export function Router() {
  return (
    <Routes>
      <Route path="/" element={<AppLayout />}>
        <Route index element={<Navigate to="/dashboard" replace />} />
        <Route path="dashboard" element={<Dashboard />} />
        <Route path="reports" element={<Reports />} />
        <Route path="activities" element={<Activities />} />
        <Route path="activities/:activityId" element={<ActivityDetail />} />
        <Route path="attention" element={<Attention />} />
      </Route>
    </Routes>
  );
}
