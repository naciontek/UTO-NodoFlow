import { Component, signal, computed, OnDestroy, provideZonelessChangeDetection } from '@angular/core';
import { bootstrapApplication } from '@angular/platform-browser';

interface Attempt { attempt_id: string; node_id: string; state: string; worker_id: string | null }
interface Task {
  task_id: string; state: string; payload: {value: string; duration_ms: number};
  result: {value: string; characters: number} | null; error: string | null; attempts: Attempt[];
}
interface NodeInfo {node_id: string; capacity: number; busy: number; available: boolean}

@Component({
  selector: 'app-root',
  standalone: true,
  template: `
    <main>
      <header><div><p class="eyebrow">UTO · ARQUITECTURA DE SOFTWARE</p>
        <h1>NodoFlow<span>Procesamiento distribuido de tareas</span></h1></div>
        <span class="badge">Prototipo local</span></header>
      <section>
        <div class="heading"><h2>Ejecutar una tarea</h2><button class="secondary" (click)="check()" [disabled]="checking()">Comprobar conexiones</button></div>
        <p>Envía un texto. Un nodo lo transforma a mayúsculas y guarda el resultado.</p>
        <form (submit)="$event.preventDefault(); submit(value.value, duration.value)">
          <label>Texto de la tarea<input #value value="Hola NodoFlow" required maxlength="500" autocomplete="off"></label>
          <label>Duración (milisegundos)<input #duration type="number" value="1000" min="100" max="10000" required step="100"></label>
          <div class="actions"><button type="submit" [disabled]="sending()">{{ sending() ? 'Enviando…' : 'Ejecutar tarea' }}</button>
          <button type="button" class="secondary" (click)="examples()" [disabled]="sending()">Crear 3 ejemplos</button></div>
        </form>
        <div class="notice" role="status">{{ message() }}</div>
        <small>{{ connection() }}</small>
      </section>
      <div class="summary">
        <section><strong>{{ tasks().length }}</strong><span>Tareas recientes</span></section>
        <section><strong>{{ running() }}</strong><span>En proceso</span></section>
        <section><strong>{{ completed() }}</strong><span>Completadas</span></section>
      </div>
      <section>
        <div class="heading"><h2>Tareas y resultados</h2><span class="muted">Actualización automática</span></div>
        @if (refreshError()) { <p role="alert">{{ refreshError() }}</p> }
        @if (!tasks().length) {
          <p class="empty">Aún no hay tareas. Usa «Crear 3 ejemplos» para ver el procesamiento.</p>
        }
        <div class="task-list">
        @for (task of tasks(); track task.task_id) {
          <article>
            <div class="heading"><strong>{{ task.payload.value }}</strong><span class="state" [class.done]="task.state === 'SUCCEEDED'">{{ label(task.state) }}</span></div>
            <p class="result">{{ task.result ? task.result.value : (task.error || 'Esperando resultado…') }}</p>
            <small>Tarea {{ task.task_id }} · {{ task.payload.duration_ms }} ms</small>
            @for (attempt of task.attempts; track attempt.attempt_id) {
              <small>Nodo {{ attempt.node_id }} · {{ label(attempt.state) }} @if (attempt.worker_id) { · {{ attempt.worker_id }} }</small>
              <details><summary>Ver intento</summary><code>{{ attempt.attempt_id }}</code></details>
            }
          </article>
        }
        </div>
      </section>
      <section><h2>Nodos de procesamiento</h2>
        <div class="nodes">
        @for (node of nodes(); track node.node_id) {
          <div><strong>Nodo {{ node.node_id }}</strong><span>{{ node.available ? 'Disponible' : 'Sin conexión' }}</span><small>{{ node.busy }} / {{ node.capacity }} workers ocupados</small></div>
        } @empty { <p>Esperando el registro de un nodo. Las tareas aceptadas permanecerán en cola.</p> }
        </div>
      </section>
      <footer>Los ejemplos se ejecutan de verdad y sus resultados permanecen guardados. Se muestran las últimas 100 tareas.</footer>
    </main>`
})
class App implements OnDestroy {
  tasks = signal<Task[]>([]);
  nodes = signal<NodeInfo[]>([]);
  sending = signal(false);
  checking = signal(false);
  message = signal('Listo para crear una tarea o cargar ejemplos.');
  connection = signal('Comprobando conexiones…');
  refreshError = signal('');
  running = computed(() => this.tasks().filter(t => ['PENDING','RUNNING'].includes(t.state)).length);
  completed = computed(() => this.tasks().filter(t => t.state === 'SUCCEEDED').length);
  private refreshing = false;
  private checkCount = 0;
  private timer: ReturnType<typeof setInterval>;
  constructor() {
    void this.check();
    void this.refresh();
    this.timer = setInterval(() => void this.refresh(), 1000);
  }
  ngOnDestroy() { clearInterval(this.timer); }
  label(state: string): string {
    return ({PENDING:'En cola', RUNNING:'En ejecución', ASSIGNED:'Asignada', SUCCEEDED:'Completada',
      FAILED:'Fallida', RETRY_PENDING:'Pendiente de reintento', ABANDONED:'Interrumpida'} as Record<string,string>)[state] || state;
  }
  async request(path: string, init: RequestInit = {}) {
    const response = await fetch('/api' + path, {...init, cache:'no-store', signal:AbortSignal.timeout(5000)});
    const data = await response.json();
    if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'No se pudo completar la operación. Revisa los datos e intenta nuevamente.');
    return data;
  }
  async check() {
    if (this.checking()) return;
    this.checking.set(true);
    this.connection.set('Comprobando conexiones…');
    try {
      const data = await this.request('/health/ready');
      this.connection.set((data.task_processing_enabled ? 'Sistema conectado.' : 'Conexiones listas; iniciando procesamiento.')
        + ' Comprobación ' + (++this.checkCount) + ' · ' + new Date().toLocaleTimeString('es-CO'));
    } catch { this.connection.set('No se pudo confirmar la conexión. Intenta nuevamente.'); }
    finally { this.checking.set(false); }
  }
  async refresh() {
    if (this.refreshing) return;
    this.refreshing = true;
    try {
      const [tasks, nodes] = await Promise.all([this.request('/tasks'), this.request('/nodes')]);
      this.tasks.set(tasks); this.nodes.set(nodes); this.refreshError.set('');
    } catch { this.refreshError.set('No se pudo actualizar la lista. Se intentará nuevamente.'); }
    finally { this.refreshing = false; }
  }
  async submit(value: string, duration: string) {
    if (this.sending()) return;
    this.sending.set(true); this.message.set('Enviando tarea…');
    try {
      const task: Task = await this.request('/tasks', {method:'POST', headers:{'Content-Type':'application/json'},
        body:JSON.stringify({payload:{value, duration_ms:Number(duration)}, idempotency_key:crypto.randomUUID()})});
      this.message.set('Tarea aceptada: ' + task.payload.value + '. Puedes seguir su resultado abajo.');
      await this.refresh();
    } catch (error) { this.message.set(error instanceof Error ? error.message : 'No se pudo enviar la tarea.'); }
    finally { this.sending.set(false); }
  }
  async examples() {
    if (this.sending()) return;
    this.sending.set(true); this.message.set('Creando tareas de ejemplo…');
    let accepted = 0;
    try {
      for (const value of ['hola nodoflow', 'procesamiento distribuido', 'tres tareas de ejemplo']) {
        await this.request('/tasks', {method:'POST', headers:{'Content-Type':'application/json'},
          body:JSON.stringify({payload:{value,duration_ms:4000},idempotency_key:crypto.randomUUID()})});
        accepted++;
      }
      this.message.set('3 tareas de ejemplo aceptadas. Sus estados y resultados se actualizan abajo.');
      await this.refresh();
    } catch { this.message.set(accepted + ' ejemplos confirmados. Hubo un error al completar el envío; revisa la lista.'); }
    finally { this.sending.set(false); }
  }
}
bootstrapApplication(App, {providers:[provideZonelessChangeDetection()]}).catch(console.error);
